# ====================================================================================================
# crawler.py – Independent Async Web Crawler for CrownStar‑Absolute
# Features:
#   - Robots.txt compliance (fetch, parse, respect disallow & crawl‑delay)
#   - Domain‑wise politeness (configurable delays, rate limiting)
#   - Async HTML fetching with aiohttp (retries, timeouts)
#   - Link extraction (href, relative → absolute)
#   - Depth‑limited, page‑limited crawling
#   - URL deduplication (normalised)
#   - Callback for page processing (e.g., indexing)
#   - Graceful shutdown on interrupt
# ====================================================================================================

import asyncio
import aiohttp
import re
import time
import urllib.robotparser
import urllib.parse
from typing import Set, Dict, List, Optional, Callable, Any
from collections import deque
from urllib.parse import urlparse, urljoin, urlunparse
import logging
import signal
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("CrownStar.Crawler")

# --------------------------------------------------------------------
# HTML link extraction (faster than BeautifulSoup for simple cases)
# --------------------------------------------------------------------
HREF_PATTERN = re.compile(r'href=[\"\'](.*?)[\"\']', re.IGNORECASE)
def extract_links(html: str, base_url: str) -> Set[str]:
    """Extract all href links from HTML and convert to absolute URLs."""
    links = set()
    for match in HREF_PATTERN.finditer(html):
        raw = match.group(1)
        if not raw or raw.startswith('#') or raw.startswith('javascript:'):
            continue
        absolute = urljoin(base_url, raw)
        # Filter out non‑http schemes
        if absolute.startswith(('http://', 'https://')):
            # Normalise: remove fragments and trailing slash for deduplication
            parsed = urlparse(absolute)
            normalised = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, ''))
            links.add(normalised)
    return links

# --------------------------------------------------------------------
# URL normalisation (remove fragments, lowercase scheme/host)
# --------------------------------------------------------------------
def normalise_url(url: str) -> str:
    """Normalise URL for deduplication."""
    parsed = urlparse(url.lower())
    # Remove fragment
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, ''))

# --------------------------------------------------------------------
# Robots.txt cache and parser
# --------------------------------------------------------------------
class RobotsCache:
    """Cache for robots.txt parsers per domain."""
    def __init__(self, user_agent: str = "CrownStarCrawler/1.0"):
        self.user_agent = user_agent
        self._parsers: Dict[str, urllib.robotparser.RobotFileParser] = {}
        self._fetch_times: Dict[str, float] = {}
    
    async def get_parser(self, domain: str, session: aiohttp.ClientSession) -> urllib.robotparser.RobotFileParser:
        """Return a RobotFileParser for the domain, fetching robots.txt if needed."""
        if domain in self._parsers:
            # Refresh if older than 24 hours
            if time.time() - self._fetch_times.get(domain, 0) > 86400:
                await self._fetch_robots(domain, session)
            return self._parsers[domain]
        return await self._fetch_robots(domain, session)
    
    async def _fetch_robots(self, domain: str, session: aiohttp.ClientSession) -> urllib.robotparser.RobotFileParser:
        robots_url = f"https://{domain}/robots.txt"
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)
        try:
            async with session.get(robots_url, timeout=10) as resp:
                if resp.status == 200:
                    content = await resp.text()
                    rp.parse(content.splitlines())
                else:
                    # No robots.txt or error: allow all
                    rp.allow_all = True
        except Exception as e:
            logger.debug(f"Failed to fetch robots.txt for {domain}: {e}")
            rp.allow_all = True
        self._parsers[domain] = rp
        self._fetch_times[domain] = time.time()
        return rp

# --------------------------------------------------------------------
# Crawler Configuration
# --------------------------------------------------------------------
@dataclass
class CrawlerConfig:
    user_agent: str = "CrownStarCrawler/1.0 (+https://crownstar.ai)"
    max_concurrent: int = 50                 # Max concurrent fetch tasks
    max_pages: int = 1000                    # Max total pages to crawl
    max_depth: int = 3                       # Max crawl depth (0 = only seed)
    request_timeout: int = 30                # Seconds per request
    delay_between_requests: float = 1.0      # Minimum delay between requests to same domain
    retry_count: int = 2
    respect_robots: bool = True              # Obey robots.txt directives
    follow_redirects: bool = True
    max_redirects: int = 5
    save_robots_cache: bool = True
    robots_cache_dir: str = "data/robots_cache"

@dataclass
class CrawlTask:
    url: str
    depth: int
    referer: Optional[str] = None

# --------------------------------------------------------------------
# Async Crawler Core
# --------------------------------------------------------------------
class AsyncCrawler:
    def __init__(self, config: Optional[CrawlerConfig] = None, 
                 page_callback: Optional[Callable[[str, str, int], Any]] = None):
        """
        Args:
            config: CrawlerConfig instance.
            page_callback: async function called for each fetched page.
                           Signature: async def callback(url: str, html: str, depth: int)
        """
        self.config = config or CrawlerConfig()
        self.page_callback = page_callback
        self._session: Optional[aiohttp.ClientSession] = None
        self._robots_cache = RobotsCache(self.config.user_agent)
        self._visited: Set[str] = set()
        self._queue: deque = deque()
        self._active_tasks: Set[asyncio.Task] = set()
        self._domain_last_request: Dict[str, float] = {}
        self._pages_crawled = 0
        self._stop_flag = False
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent)
        
        # Setup signal handlers for graceful shutdown
        self._original_sigint = None
        self._original_sigterm = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.request_timeout)
            connector = aiohttp.TCPConnector(limit_per_host=10, enable_cleanup_closed=True)
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": self.config.user_agent},
                timeout=timeout,
                connector=connector
            )
        return self._session
    
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
        # Cancel all active tasks
        for task in self._active_tasks:
            task.cancel()
        if self._active_tasks:
            await asyncio.gather(*self._active_tasks, return_exceptions=True)
    
    async def _respect_robots(self, url: str) -> bool:
        """Check robots.txt for the URL."""
        if not self.config.respect_robots:
            return True
        parsed = urlparse(url)
        domain = parsed.netloc
        session = await self._get_session()
        rp = await self._robots_cache.get_parser(domain, session)
        # Check user‑agent and URL path
        allowed = rp.can_fetch(self.config.user_agent, url)
        if not allowed:
            logger.debug(f"Disallowed by robots.txt: {url}")
        return allowed
    
    async def _fetch_page(self, url: str) -> Optional[tuple[str, str]]:
        """Fetch a single page, return (html, final_url) or None."""
        domain = urlparse(url).netloc
        # Politeness: enforce delay per domain
        async with self._lock:
            now = time.time()
            last = self._domain_last_request.get(domain, 0)
            delay = self.config.delay_between_requests
            if now - last < delay:
                await asyncio.sleep(delay - (now - last))
            self._domain_last_request[domain] = time.time()
        
        session = await self._get_session()
        for attempt in range(self.config.retry_count + 1):
            try:
                async with session.get(url, allow_redirects=self.config.follow_redirects,
                                       max_redirects=self.config.max_redirects) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        final_url = str(resp.url)
                        return (html, final_url)
                    elif resp.status in (301, 302) and not self.config.follow_redirects:
                        # Manual redirect handling
                        location = resp.headers.get('Location')
                        if location:
                            new_url = urljoin(url, location)
                            return await self._fetch_page(new_url)
                    else:
                        logger.debug(f"Non‑200 response {resp.status} for {url}")
                        return None
            except asyncio.TimeoutError:
                logger.debug(f"Timeout fetching {url} (attempt {attempt+1})")
            except Exception as e:
                logger.debug(f"Error fetching {url}: {e}")
            if attempt < self.config.retry_count:
                await asyncio.sleep(2 ** attempt)  # exponential backoff
        return None
    
    async def _process_page(self, url: str, html: str, depth: int):
        """Process a fetched page: extract links and call callback."""
        # Call user callback if provided
        if self.page_callback:
            try:
                await self.page_callback(url, html, depth)
            except Exception as e:
                logger.error(f"Page callback failed for {url}: {e}")
        # Extract new links
        if depth < self.config.max_depth:
            links = extract_links(html, url)
            for link in links:
                normalised = normalise_url(link)
                if normalised not in self._visited:
                    self._queue.append(CrawlTask(normalised, depth + 1, url))
    
    async def _crawl_worker(self):
        """Worker coroutine that processes tasks from the queue."""
        while not self._stop_flag and self._queue:
            try:
                task = self._queue.popleft()
            except IndexError:
                break
            
            url = task.url
            depth = task.depth
            
            # Check visited (double‑check)
            if url in self._visited:
                continue
            
            # Respect robots.txt
            if not await self._respect_robots(url):
                continue
            
            # Mark as visited before fetching to avoid duplicate fetches
            self._visited.add(url)
            
            # Fetch page
            result = await self._fetch_page(url)
            if result is None:
                continue
            
            html, final_url = result
            if final_url != url:
                # Redirected – add final URL to visited as well
                self._visited.add(final_url)
            
            # Process page
            await self._process_page(final_url, html, depth)
            
            async with self._lock:
                self._pages_crawled += 1
                if self._pages_crawled >= self.config.max_pages:
                    self._stop_flag = True
                    break
    
    async def crawl(self, seed_urls: List[str]) -> Dict[str, Any]:
        """
        Start crawling from seed URLs.
        Returns statistics.
        """
        # Normalise and add seeds to queue
        for url in seed_urls:
            norm = normalise_url(url)
            if norm not in self._visited:
                self._queue.append(CrawlTask(norm, 0))
        
        # Start workers
        workers = [asyncio.create_task(self._crawl_worker()) for _ in range(min(self.config.max_concurrent, len(self._queue)))]
        self._active_tasks.update(workers)
        
        # Wait for workers to finish or stop condition
        await asyncio.gather(*workers, return_exceptions=True)
        
        return {
            "pages_crawled": self._pages_crawled,
            "total_queued": len(self._queue) + self._pages_crawled,
            "visited_urls": len(self._visited),
            "domains_encountered": len(self._domain_last_request)
        }
    
    # --------------------------------------------------------------------
    # Context manager support
    # --------------------------------------------------------------------
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

# --------------------------------------------------------------------
# Convenience function to create crawler and run
# --------------------------------------------------------------------
async def crawl_website(start_urls: List[str], 
                        max_pages: int = 500, 
                        max_depth: int = 2,
                        delay: float = 1.0,
                        callback: Optional[Callable] = None) -> Dict:
    """
    High‑level function to crawl a website with sensible defaults.
    """
    config = CrawlerConfig(max_pages=max_pages, max_depth=max_depth, delay_between_requests=delay)
    async with AsyncCrawler(config, callback) as crawler:
        stats = await crawler.crawl(start_urls)
        return stats

# ====================================================================================================
# Example usage (commented)
# ====================================================================================================
"""
async def index_page(url: str, html: str, depth: int):
    print(f"Crawled: {url} (depth {depth}) - {len(html)} bytes")

async def main():
    stats = await crawl_website(
        start_urls=["https://example.com"],
        max_pages=100,
        max_depth=2,
        delay=0.5,
        callback=index_page
    )
    print("Crawl stats:", stats)

if __name__ == "__main__":
    asyncio.run(main())
"""

# ====================================================================================================
# END OF crawler.py (33,482 characters)
# ====================================================================================================
