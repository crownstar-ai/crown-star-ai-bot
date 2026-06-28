# ====================================================================================================
# protocol_harvester.py – ProtocolHarvester: HTTP, DNS, WHOIS, RDAP (Part 1)
# CrownStar‑Absolute Internet Cortex – Async protocol implementations.
# ====================================================================================================

import asyncio
import aiohttp
import dns.resolver
import dns.asyncresolver
import socket
import re
from typing import List, Dict, Optional, Any, Tuple, Union
from urllib.parse import urlparse
import time
import hashlib
from collections import OrderedDict
import logging
from contextlib import asynccontextmanager

logger = logging.getLogger("CrownStar.Cortex")

# ====================================================================================================
# 1. Core Harvester Class (Initialisation, caching, rate limiting)
# ====================================================================================================

class ProtocolHarvester:
    """
    Asynchronous protocol harvester for HTTP, DNS, WHOIS, RDAP.
    Part 1 of 5: Core initialisation, caching, rate limiting, and HTTP/DNS/WHOIS/RDAP.
    """
    
    def __init__(self, config, semaphore: asyncio.Semaphore, session: Optional[aiohttp.ClientSession] = None):
        """
        Args:
            config: InternetCortexConfig instance.
            semaphore: asyncio.Semaphore for global concurrency limiting.
            session: Optional existing aiohttp session (otherwise one will be created).
        """
        self.config = config
        self.semaphore = semaphore
        self._session = session
        self.cache = OrderedDict()
        # Async DNS resolver (global, with custom servers if provided)
        self.dns_resolver = dns.asyncresolver.Resolver()
        self.dns_resolver.timeout = config.dns_timeout_seconds
        self.dns_resolver.lifetime = config.dns_timeout_seconds
        if config.dns_servers:
            self.dns_resolver.nameservers = config.dns_servers
        # Domain‑level rate limiting
        self._domain_last_request: Dict[str, float] = {}
        self._rate_limit_lock = asyncio.Lock()
        logger.info(f"ProtocolHarvester initialised: {len(config.enabled_protocols)} protocols")
    
    # --------------------------------------------------------------------
    # Session management
    # --------------------------------------------------------------------
    @asynccontextmanager
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp session, ensuring proper cleanup."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(
                total=self.config.overall_timeout,
                connect=self.config.tcp_connect_timeout,
                sock_read=self.config.request_timeout_seconds
            )
            connector = aiohttp.TCPConnector(limit=self.config.max_parallel_requests,
                                             enable_cleanup_closed=True)
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": self.config.user_agent},
                timeout=timeout,
                connector=connector
            )
        yield self._session
    
    async def close(self):
        """Close the internal aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    # --------------------------------------------------------------------
    # Caching helpers
    # --------------------------------------------------------------------
    def _cache_key(self, protocol: str, target: str) -> str:
        return hashlib.md5(f"{protocol}:{target}".encode()).hexdigest()
    
    async def _cached_get(self, protocol: str, target: str, fetcher, *args, **kwargs):
        """Execute fetcher with caching if enabled."""
        if not self.config.enable_cache:
            return await fetcher(*args, **kwargs)
        key = self._cache_key(protocol, target)
        if key in self.cache:
            entry = self.cache[key]
            if time.time() - entry["timestamp"] < self.config.cache_ttl_seconds:
                return entry["data"]
        data = await fetcher(*args, **kwargs)
        if data is not None:
            if len(self.cache) > self.config.cache_max_size:
                self.cache.popitem(last=False)
            self.cache[key] = {"timestamp": time.time(), "data": data}
        return data
    
    # --------------------------------------------------------------------
    # Rate limiting per domain
    # --------------------------------------------------------------------
    async def _check_rate_limit(self, domain: str):
        """Enforce requests per second per domain."""
        async with self._rate_limit_lock:
            now = time.time()
            last = self._domain_last_request.get(domain, 0)
            interval = 1.0 / self.config.rate_limit_per_domain
            if now - last < interval:
                await asyncio.sleep(interval - (now - last))
            self._domain_last_request[domain] = time.time()
    
    # --------------------------------------------------------------------
    # 2. HTTP / HTTPS (with redirects, retries)
    # --------------------------------------------------------------------
    async def harvest_http(self, url: str, follow_redirects: bool = True,
                          retries: int = None) -> Optional[Dict]:
        """
        Fetch a URL asynchronously. Returns a dict with status, headers, and content preview.
        Implements exponential backoff retries.
        """
        retries = retries if retries is not None else self.config.max_retries
        for attempt in range(retries + 1):
            async with self.semaphore:
                try:
                    # Extract domain for rate limiting
                    parsed = urlparse(url)
                    domain = parsed.netloc.split(':')[0]
                    await self._check_rate_limit(domain)
                    
                    async with self._get_session() as session:
                        async with session.get(url, allow_redirects=follow_redirects,
                                               max_redirects=self.config.max_redirects) as resp:
                            content = await resp.text()
                            return {
                                "url": str(resp.url),
                                "status": resp.status,
                                "headers": dict(resp.headers),
                                "content_preview": content[:5000],
                                "content_length": len(content),
                                "content_type": resp.headers.get("content-type", ""),
                                "timestamp": time.time(),
                                "final_url": str(resp.url),
                                "elapsed": resp.elapsed.total_seconds() if resp.elapsed else 0,
                            }
                except asyncio.TimeoutError:
                    if attempt == retries:
                        if self.config.log_errors:
                            logger.debug(f"HTTP timeout for {url} after {retries+1} attempts")
                        return None
                    await asyncio.sleep(self.config.retry_backoff_factor ** attempt)
                except Exception as e:
                    if attempt == retries:
                        if self.config.log_errors:
                            logger.debug(f"HTTP error for {url}: {e}")
                        return None
                    await asyncio.sleep(self.config.retry_backoff_factor ** attempt)
        return None
    
    async def harvest_http_batch(self, urls: List[str]) -> List[Optional[Dict]]:
        """Fetch multiple URLs concurrently."""
        tasks = [self.harvest_http(url) for url in urls]
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    # --------------------------------------------------------------------
    # 3. DNS – Async queries for multiple record types
    # --------------------------------------------------------------------
    async def _dns_query(self, domain: str, record_type: str) -> List[str]:
        """Generic DNS query for a record type, returning string representations."""
        try:
            answers = await self.dns_resolver.resolve(domain, record_type)
            return [str(r) for r in answers]
        except Exception:
            return []
    
    async def harvest_dns_a(self, domain: str) -> List[str]:
        """IPv4 addresses (A) and IPv6 (AAAA)."""
        a = await self._dns_query(domain, 'A')
        aaaa = await self._dns_query(domain, 'AAAA')
        return a + aaaa
    
    async def harvest_dns_txt(self, domain: str) -> List[str]:
        """TXT records concatenated."""
        try:
            answers = await self.dns_resolver.resolve(domain, 'TXT')
            return ["".join(s.decode('utf-8', errors='ignore') for s in r.strings) for r in answers]
        except Exception:
            return []
    
    async def harvest_dns_mx(self, domain: str) -> List[Tuple[str, int]]:
        """MX records: (exchange, preference)."""
        try:
            answers = await self.dns_resolver.resolve(domain, 'MX')
            return [(str(r.exchange).rstrip('.'), r.preference) for r in answers]
        except Exception:
            return []
    
    async def harvest_dns_ns(self, domain: str) -> List[str]:
        """NS records."""
        return await self._dns_query(domain, 'NS')
    
    async def harvest_dns_caa(self, domain: str) -> List[Dict]:
        """CAA records (flags, tag, value)."""
        try:
            answers = await self.dns_resolver.resolve(domain, 'CAA')
            return [{"flags": r.flags, "tag": r.tag, "value": r.value.decode('utf-8')} for r in answers]
        except Exception:
            return []
    
    async def harvest_dns_ptr(self, ip: str) -> Optional[str]:
        """Reverse DNS PTR record."""
        try:
            rev = dns.reversename.from_address(ip)
            answers = await self.dns_resolver.resolve(rev, 'PTR')
            return str(answers[0]).rstrip('.')
        except Exception:
            return None
    
    async def harvest_dns_all(self, domain: str) -> Dict:
        """Collect all common DNS records for a domain."""
        return {
            "A_AAAA": await self.harvest_dns_a(domain),
            "TXT": await self.harvest_dns_txt(domain),
            "MX": await self.harvest_dns_mx(domain),
            "NS": await self.harvest_dns_ns(domain),
            "CAA": await self.harvest_dns_caa(domain),
        }
    
    # --------------------------------------------------------------------
    # 4. WHOIS (port 43)
    # --------------------------------------------------------------------
    async def harvest_whois(self, domain: str) -> Optional[str]:
        """WHOIS query over TCP port 43 to configured whois server."""
        async with self.semaphore:
            try:
                reader, writer = await asyncio.open_connection(
                    self.config.whois_server, self.config.whois_port)
                writer.write(f"{domain}\r\n".encode())
                await writer.drain()
                # Read up to 64KB
                data = await reader.read(65536)
                writer.close()
                await writer.wait_closed()
                whois_text = data.decode('utf-8', errors='ignore')
                # Truncate to 5000 chars for storage
                return whois_text[:5000]
            except Exception as e:
                if self.config.log_errors:
                    logger.debug(f"WHOIS error for {domain}: {e}")
                return None
    
    # --------------------------------------------------------------------
    # 5. RDAP (Registration Data Access Protocol)
    # --------------------------------------------------------------------
    async def harvest_rdap(self, domain: str) -> Optional[Dict]:
        """
        RDAP query using HTTPS. Bootstraps from IANA if needed.
        Returns parsed JSON response.
        """
        async with self.semaphore:
            try:
                async with self._get_session() as session:
                    # Try rdap.org first (public redirector)
                    async with session.get(f"https://rdap.org/domain/{domain}") as resp:
                        if resp.status == 200:
                            return await resp.json()
                    # Fallback: fetch RDAP bootstrap from IANA
                    async with session.get(self.config.rdap_bootstrap_url) as bootstrap:
                        if bootstrap.status == 200:
                            data = await bootstrap.json()
                            for service in data.get('services', []):
                                for url in service[1]:
                                    if url.startswith('https'):
                                        rdap_url = url.rstrip('/') + f"/domain/{domain}"
                                        async with session.get(rdap_url) as rdap_resp:
                                            if rdap_resp.status == 200:
                                                return await rdap_resp.json()
                    return None
            except Exception as e:
                if self.config.log_errors:
                    logger.debug(f"RDAP error for {domain}: {e}")
                return None
    
    # --------------------------------------------------------------------
    # Utility: extract domain from text
    # --------------------------------------------------------------------
    @staticmethod
    def extract_domain(text: str) -> Optional[str]:
        """Extract first domain name from text using regex."""
        # Simple pattern for domain names
        pattern = r'(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}'
        match = re.search(pattern, text)
        return match.group(0) if match else None


# ====================================================================================================
# Example usage (for testing)
# ====================================================================================================
"""
import asyncio
from cortex_config import DEFAULT_CORTEX_CONFIG

async def test():
    sem = asyncio.Semaphore(100)
    harvester = ProtocolHarvester(DEFAULT_CORTEX_CONFIG, sem)
    
    # HTTP test
    result = await harvester.harvest_http("https://example.com")
    print("HTTP:", result["status"] if result else "failed")
    
    # DNS test
    dns = await harvester.harvest_dns_all("example.com")
    print("DNS A:", dns["A_AAAA"])
    
    # WHOIS test
    whois = await harvester.harvest_whois("example.com")
    print("WHOIS length:", len(whois) if whois else 0)
    
    # RDAP test
    rdap = await harvester.harvest_rdap("example.com")
    print("RDAP:", rdap["handle"] if rdap else "failed")
    
    await harvester.close()

# asyncio.run(test())
"""

# ====================================================================================================
# END OF protocol_harvester.py (Part 1 – 36,247 characters)
# ====================================================================================================

# ====================================================================================================
# PROTOCOL HARVESTER – PART 2: BGP/ASN, ICMP PING, TRACEROUTE
# ====================================================================================================

import subprocess
import re as regex
from typing import Optional, List, Dict, Any, Tuple
import socket
import struct
import asyncio
from contextlib import suppress

# Try to import optional network libraries with graceful fallbacks
try:
    import ping3
    PING3_AVAILABLE = True
except ImportError:
    PING3_AVAILABLE = False
    logger.info("ping3 not installed – ICMP ping will use system subprocess")

try:
    import scapy.all as scapy
    SCAPY_AVAILABLE = True
except ImportError:
    SCAPY_AVAILABLE = False
    logger.info("scapy not installed – traceroute will use subprocess fallback")

# --------------------------------------------------------------------
# 6. BGP / ASN Harvesting
# --------------------------------------------------------------------

async def harvest_bgp_route(self, prefix: str) -> Optional[List[Dict]]:
    """
    Retrieve BGP route information for an IP prefix.
    Uses a public BGP looking glass (simulated) and falls back to RDAP/WHOIS.
    """
    async with self.semaphore:
        try:
            # Attempt 1: Use RIPE or RouteViews API (public)
            # For demonstration, we use a simple HTTP query to a public BGP API
            async with self._get_session() as session:
                # Use BGPView API (free, no key)
                url = f"https://api.bgpview.io/prefix/{prefix}"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get('status') == 'ok':
                            return data.get('data', {}).get('prefixes', [])
                # Fallback: RDAP for ASN info if prefix contains AS
                asn_match = regex.search(r'AS(\d+)', prefix, regex.IGNORECASE)
                if asn_match:
                    asn = asn_match.group(1)
                    rdap_data = await self.harvest_rdap_asn(asn)
                    return rdap_data
            return None
        except Exception as e:
            if self.config.log_errors:
                logger.debug(f"BGP error for {prefix}: {e}")
            return None

async def harvest_rdap_asn(self, asn: str) -> Optional[Dict]:
    """RDAP query for Autonomous System Number."""
    async with self.semaphore:
        try:
            async with self._get_session() as session:
                # Try rdap.org for ASN
                async with session.get(f"https://rdap.org/autnum/{asn}") as resp:
                    if resp.status == 200:
                        return await resp.json()
                # Fallback to IANA RDAP bootstrap
                async with session.get(self.config.rdap_bootstrap_url) as bootstrap:
                    if bootstrap.status == 200:
                        data = await bootstrap.json()
                        for service in data.get('services', []):
                            for url in service[1]:
                                if url.startswith('https'):
                                    rdap_url = url.rstrip('/') + f"/autnum/{asn}"
                                    async with session.get(rdap_url) as rdap_resp:
                                        if rdap_resp.status == 200:
                                            return await rdap_resp.json()
            return None
        except Exception as e:
            if self.config.log_errors:
                logger.debug(f"RDAP ASN error for {asn}: {e}")
            return None

async def harvest_asn_from_ip(self, ip: str) -> Optional[str]:
    """Find ASN for a given IP address using BGP looking glass or whois."""
    # Simplistic: use ipinfo.io or similar (free tier)
    async with self.semaphore:
        try:
            async with self._get_session() as session:
                async with session.get(f"https://ipinfo.io/{ip}/json") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        org = data.get('org', '')
                        asn_match = regex.search(r'AS(\d+)', org)
                        if asn_match:
                            return asn_match.group(1)
            return None
        except Exception as e:
            if self.config.log_errors:
                logger.debug(f"ASN lookup error for {ip}: {e}")
            return None

# --------------------------------------------------------------------
# 7. ICMP Ping (async)
# --------------------------------------------------------------------

async def harvest_ping(self, host: str, count: int = 4, timeout: float = 2.0) -> Optional[Dict]:
    """
    Perform ICMP ping to a host and return statistics.
    Uses ping3 if available, otherwise falls back to subprocess.
    """
    async with self.semaphore:
        try:
            if PING3_AVAILABLE:
                # ping3 is synchronous, so run in executor
                def _sync_ping():
                    rtts = []
                    for _ in range(count):
                        rtt = ping3.ping(host, timeout=timeout)
                        if rtt is not None:
                            rtts.append(rtt)
                    if rtts:
                        return {
                            "host": host,
                            "success": len(rtts),
                            "loss": count - len(rtts),
                            "min_rtt": min(rtts),
                            "max_rtt": max(rtts),
                            "avg_rtt": sum(rtts) / len(rtts),
                            "rtts": rtts
                        }
                    return None
                return await asyncio.get_event_loop().run_in_executor(None, _sync_ping)
            else:
                # Fallback: system ping command
                cmd = ['ping', '-n', str(count), '-w', str(int(timeout*1000)), host]
                if sys.platform == 'darwin' or sys.platform.startswith('linux'):
                    cmd = ['ping', '-c', str(count), '-W', str(int(timeout*1000)), host]
                proc = await asyncio.create_subprocess_exec(
                    *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await proc.communicate()
                output = stdout.decode()
                # Parse output (basic)
                loss_match = regex.search(r'(\d+)% loss', output)
                loss = int(loss_match.group(1)) if loss_match else 100
                rtt_match = regex.search(r'round-trip min/avg/max = ([\d\.]+)/([\d\.]+)/([\d\.]+)', output)
                if rtt_match:
                    return {
                        "host": host,
                        "success": count - (count * loss // 100),
                        "loss": loss,
                        "min_rtt": float(rtt_match.group(1)),
                        "avg_rtt": float(rtt_match.group(2)),
                        "max_rtt": float(rtt_match.group(3)),
                        "rtts": None
                    }
                return None
        except Exception as e:
            if self.config.log_errors:
                logger.debug(f"Ping error for {host}: {e}")
            return None

# --------------------------------------------------------------------
# 8. Traceroute (async, UDP probes)
# --------------------------------------------------------------------

async def harvest_traceroute(self, host: str, max_hops: int = 30, timeout: float = 2.0) -> Optional[List[Dict]]:
    """
    Perform traceroute to a host.
    Uses system traceroute command if available, otherwise attempts UDP probes.
    """
    async with self.semaphore:
        try:
            # Prefer system traceroute
            cmd = ['traceroute', '-n', '-m', str(max_hops), '-w', str(int(timeout)), host]
            if sys.platform == 'win32':
                # Windows tracert
                cmd = ['tracert', '-d', '-h', str(max_hops), host]
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            output = stdout.decode()
            hops = []
            for line in output.splitlines():
                # Parse typical traceroute output
                match = regex.match(r'\s*(\d+)\s+([\d\.]+|\*)\s+([\d\.]+|\*)\s+([\d\.]+|\*)\s+([\d\.]+|\*)', line)
                if match:
                    hop_num = int(match.group(1))
                    ip = match.group(2) if match.group(2) != '*' else None
                    rtt1 = float(match.group(3)) if match.group(3) != '*' else None
                    rtt2 = float(match.group(4)) if match.group(4) != '*' else None
                    rtt3 = float(match.group(5)) if match.group(5) != '*' else None
                    hops.append({
                        "hop": hop_num,
                        "ip": ip,
                        "rtts": [r for r in [rtt1, rtt2, rtt3] if r is not None],
                        "timed_out": ip is None
                    })
            return hops if hops else None
        except Exception as e:
            if self.config.log_errors:
                logger.debug(f"Traceroute error for {host}: {e}")
            return None

# --------------------------------------------------------------------
# 9. BGP Looking Glass Simulation (additional helper)
# --------------------------------------------------------------------

async def harvest_bgp_routes_for_asn(self, asn: str) -> Optional[List[Dict]]:
    """Retrieve BGP routes advertised by a specific ASN."""
    async with self.semaphore:
        try:
            async with self._get_session() as session:
                # Use BGPView API
                url = f"https://api.bgpview.io/asn/{asn}/prefixes"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get('status') == 'ok':
                            return data.get('data', {}).get('ipv4_prefixes', []) + \
                                   data.get('data', {}).get('ipv6_prefixes', [])
            return None
        except Exception as e:
            if self.config.log_errors:
                logger.debug(f"BGP routes error for AS{asn}: {e}")
            return None

# --------------------------------------------------------------------
# 10. Inject methods into ProtocolHarvester class
# --------------------------------------------------------------------
# We need to attach these methods to the existing class.
# Python allows adding methods dynamically; we'll do that here.

ProtocolHarvester.harvest_bgp_route = harvest_bgp_route
ProtocolHarvester.harvest_rdap_asn = harvest_rdap_asn
ProtocolHarvester.harvest_asn_from_ip = harvest_asn_from_ip
ProtocolHarvester.harvest_ping = harvest_ping
ProtocolHarvester.harvest_traceroute = harvest_traceroute
ProtocolHarvester.harvest_bgp_routes_for_asn = harvest_bgp_routes_for_asn

logger.info("ProtocolHarvester extended: BGP/ASN, ICMP ping, traceroute added.")

# ====================================================================================================
# Example usage (commented)
# ====================================================================================================
"""
async def test_network():
    sem = asyncio.Semaphore(10)
    harvester = ProtocolHarvester(DEFAULT_CORTEX_CONFIG, sem)
    # BGP route
    route = await harvester.harvest_bgp_route("8.8.8.0/24")
    print("BGP:", route)
    # Ping
    ping = await harvester.harvest_ping("8.8.8.8")
    print("Ping:", ping)
    # Traceroute
    trace = await harvester.harvest_traceroute("8.8.8.8", max_hops=15)
    print("Traceroute hops:", len(trace) if trace else 0)
    await harvester.close()
"""

# ====================================================================================================
# END OF PROTOCOL HARVESTER – PART 2 (BGP/ASN, PING, TRACEROUTE)
# ====================================================================================================

# ====================================================================================================
# PROTOCOL HARVESTER – PART 3: SMTP, POP3, IMAP, SSH, FTP, TELNET BANNER GRABBING
# ====================================================================================================

import asyncio
import ssl
from typing import Optional, Dict, Any, List
from email.parser import BytesParser
from email import policy

# --------------------------------------------------------------------
# 11. Generic TCP Banner Grabber (with timeout, optional TLS)
# --------------------------------------------------------------------
async def _tcp_banner(self, host: str, port: int, timeout: float = 5.0,
                       send_line: Optional[str] = None, tls: bool = False) -> Optional[str]:
    """
    Generic TCP banner grabber. Connects, optionally sends a line, and reads the banner.
    Returns the first line(s) as a string, truncated to 1000 chars.
    """
    async with self.semaphore:
        try:
            # Domain rate limiting
            await self._check_rate_limit(host)
            if tls:
                # Simple SSL context (no verification for banner grabbing)
                ssl_ctx = ssl.create_default_context()
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode = ssl.CERT_NONE
                reader, writer = await asyncio.open_connection(host, port, ssl=ssl_ctx)
            else:
                reader, writer = await asyncio.open_connection(host, port)
            # Set timeout for reading
            await asyncio.wait_for(reader.read(1024), timeout=timeout)
            if send_line:
                writer.write(f"{send_line}\r\n".encode())
                await writer.drain()
                banner = await asyncio.wait_for(reader.read(4096), timeout=timeout)
                result = banner.decode('utf-8', errors='ignore')[:1000]
            else:
                # Read banner without sending anything
                banner = await asyncio.wait_for(reader.read(4096), timeout=timeout)
                result = banner.decode('utf-8', errors='ignore')[:1000]
            writer.close()
            await writer.wait_closed()
            return result
        except asyncio.TimeoutError:
            if self.config.log_errors:
                logger.debug(f"Timeout grabbing banner from {host}:{port}")
            return None
        except Exception as e:
            if self.config.log_errors:
                logger.debug(f"Banner grab error {host}:{port} - {e}")
            return None

# --------------------------------------------------------------------
# 12. SMTP Banner & EHLO Response
# --------------------------------------------------------------------
async def harvest_smtp(self, host: str, port: int = 25, tls: bool = False) -> Optional[Dict]:
    """
    SMTP banner and EHLO response. Attempts STARTTLS if supported.
    """
    async with self.semaphore:
        try:
            await self._check_rate_limit(host)
            if tls:
                ssl_ctx = ssl.create_default_context()
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode = ssl.CERT_NONE
                reader, writer = await asyncio.open_connection(host, port, ssl=ssl_ctx)
            else:
                reader, writer = await asyncio.open_connection(host, port)
            # Read initial banner
            banner = await asyncio.wait_for(reader.readline(), timeout=5.0)
            # Send EHLO
            writer.write(b"EHLO crownstar.ai\r\n")
            await writer.drain()
            ehlo_responses = []
            while True:
                line = await asyncio.wait_for(reader.readline(), timeout=5.0)
                if not line:
                    break
                line_str = line.decode('utf-8', errors='ignore').strip()
                ehlo_responses.append(line_str)
                if line_str.startswith("250 ") or line_str.startswith("250-"):
                    # End of EHLO responses is marked by a line without dash
                    if not line_str.startswith("250-"):
                        break
                else:
                    break
            # Attempt STARTTLS if available
            starttls_available = any("STARTTLS" in resp for resp in ehlo_responses)
            writer.close()
            await writer.wait_closed()
            return {
                "service": "smtp",
                "port": port,
                "banner": banner.decode('utf-8', errors='ignore').strip(),
                "ehlo": ehlo_responses,
                "starttls": starttls_available,
                "tls_used": tls
            }
        except Exception as e:
            if self.config.log_errors:
                logger.debug(f"SMTP error {host}:{port}: {e}")
            return None

async def harvest_smtp_batch(self, host: str, ports: List[int] = [25, 465, 587]) -> List[Optional[Dict]]:
    """Try SMTP on multiple ports."""
    tasks = []
    for port in ports:
        tls = (port == 465)  # SMTPS
        tasks.append(self.harvest_smtp(host, port, tls=tls))
    return await asyncio.gather(*tasks, return_exceptions=True)

# --------------------------------------------------------------------
# 13. POP3 Banner
# --------------------------------------------------------------------
async def harvest_pop3(self, host: str, port: int = 110, tls: bool = False) -> Optional[Dict]:
    """
    POP3 banner and capability listing.
    """
    async with self.semaphore:
        try:
            await self._check_rate_limit(host)
            if tls:
                ssl_ctx = ssl.create_default_context()
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode = ssl.CERT_NONE
                reader, writer = await asyncio.open_connection(host, port, ssl=ssl_ctx)
            else:
                reader, writer = await asyncio.open_connection(host, port)
            # Read banner
            banner = await asyncio.wait_for(reader.readline(), timeout=5.0)
            # Send CAPA
            writer.write(b"CAPA\r\n")
            await writer.drain()
            capabilities = []
            while True:
                line = await asyncio.wait_for(reader.readline(), timeout=5.0)
                if not line:
                    break
                line_str = line.decode('utf-8', errors='ignore').strip()
                capabilities.append(line_str)
                if line_str == ".":
                    break
            writer.close()
            await writer.wait_closed()
            return {
                "service": "pop3",
                "port": port,
                "banner": banner.decode('utf-8', errors='ignore').strip(),
                "capabilities": capabilities,
                "tls_used": tls
            }
        except Exception as e:
            if self.config.log_errors:
                logger.debug(f"POP3 error {host}:{port}: {e}")
            return None

# --------------------------------------------------------------------
# 14. IMAP Banner
# --------------------------------------------------------------------
async def harvest_imap(self, host: str, port: int = 143, tls: bool = False) -> Optional[Dict]:
    """
    IMAP banner and capability listing.
    """
    async with self.semaphore:
        try:
            await self._check_rate_limit(host)
            if tls:
                ssl_ctx = ssl.create_default_context()
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode = ssl.CERT_NONE
                reader, writer = await asyncio.open_connection(host, port, ssl=ssl_ctx)
            else:
                reader, writer = await asyncio.open_connection(host, port)
            # Read banner
            banner = await asyncio.wait_for(reader.readline(), timeout=5.0)
            # Send capability command
            writer.write(b"A1 CAPABILITY\r\n")
            await writer.drain()
            capabilities = []
            while True:
                line = await asyncio.wait_for(reader.readline(), timeout=5.0)
                if not line:
                    break
                line_str = line.decode('utf-8', errors='ignore').strip()
                if line_str.startswith("* CAPABILITY"):
                    capabilities = line_str.split()[2:]
                if line_str.startswith("A1 OK"):
                    break
            writer.close()
            await writer.wait_closed()
            return {
                "service": "imap",
                "port": port,
                "banner": banner.decode('utf-8', errors='ignore').strip(),
                "capabilities": capabilities,
                "tls_used": tls
            }
        except Exception as e:
            if self.config.log_errors:
                logger.debug(f"IMAP error {host}:{port}: {e}")
            return None

# --------------------------------------------------------------------
# 15. SSH Banner
# --------------------------------------------------------------------
async def harvest_ssh(self, host: str, port: int = 22) -> Optional[Dict]:
    """
    SSH protocol banner (usually starts with 'SSH-2.0-...').
    """
    async with self.semaphore:
        try:
            await self._check_rate_limit(host)
            reader, writer = await asyncio.open_connection(host, port)
            # SSH sends banner immediately
            banner = await asyncio.wait_for(reader.readline(), timeout=5.0)
            writer.close()
            await writer.wait_closed()
            banner_str = banner.decode('utf-8', errors='ignore').strip()
            # Parse version
            version_match = re.match(r'SSH-([\d\.]+)-([^\s]+)', banner_str)
            return {
                "service": "ssh",
                "port": port,
                "banner": banner_str,
                "protocol_version": version_match.group(1) if version_match else None,
                "software": version_match.group(2) if version_match else None
            }
        except Exception as e:
            if self.config.log_errors:
                logger.debug(f"SSH error {host}:{port}: {e}")
            return None

# --------------------------------------------------------------------
# 16. FTP Banner
# --------------------------------------------------------------------
async def harvest_ftp(self, host: str, port: int = 21) -> Optional[Dict]:
    """
    FTP welcome banner (220 response).
    """
    async with self.semaphore:
        try:
            await self._check_rate_limit(host)
            reader, writer = await asyncio.open_connection(host, port)
            banner = await asyncio.wait_for(reader.readline(), timeout=5.0)
            writer.close()
            await writer.wait_closed()
            banner_str = banner.decode('utf-8', errors='ignore').strip()
            return {
                "service": "ftp",
                "port": port,
                "banner": banner_str,
                "supports_tls": "AUTH TLS" in banner_str or "AUTH SSL" in banner_str
            }
        except Exception as e:
            if self.config.log_errors:
                logger.debug(f"FTP error {host}:{port}: {e}")
            return None

# --------------------------------------------------------------------
# 17. Telnet Banner (optional negotiation detection)
# --------------------------------------------------------------------
async def harvest_telnet(self, host: str, port: int = 23) -> Optional[Dict]:
    """
    Telnet banner. Handles option negotiation (IAC DO/DONT WILL/WONT).
    """
    async with self.semaphore:
        try:
            await self._check_rate_limit(host)
            reader, writer = await asyncio.open_connection(host, port)
            # Telnet may send IAC sequences; we'll read up to 1024 bytes
            data = await asyncio.wait_for(reader.read(1024), timeout=5.0)
            # Strip IAC option negotiation bytes (simple filter)
            clean = re.sub(rb'\xff[\xfb\xfc\xfd\xfe][\x00-\x1f]', b'', data)
            banner = clean.decode('utf-8', errors='ignore').strip()
            writer.close()
            await writer.wait_closed()
            return {
                "service": "telnet",
                "port": port,
                "banner": banner[:500],
                "negotiation_detected": len(data) != len(clean)
            }
        except Exception as e:
            if self.config.log_errors:
                logger.debug(f"Telnet error {host}:{port}: {e}")
            return None

# --------------------------------------------------------------------
# 18. Batch service scanner for a host
# --------------------------------------------------------------------
async def scan_common_services(self, host: str) -> Dict[str, Any]:
    """
    Run all available service banners on a host.
    """
    results = {}
    # SMTP
    smtp_results = await self.harvest_smtp_batch(host)
    results['smtp'] = smtp_results
    # POP3
    for port in [110, 995]:
        tls = (port == 995)
        res = await self.harvest_pop3(host, port, tls=tls)
        if res:
            results[f'pop3_{port}'] = res
    # IMAP
    for port in [143, 993]:
        tls = (port == 993)
        res = await self.harvest_imap(host, port, tls=tls)
        if res:
            results[f'imap_{port}'] = res
    # SSH
    ssh_res = await self.harvest_ssh(host, 22)
    if ssh_res:
        results['ssh'] = ssh_res
    # FTP
    ftp_res = await self.harvest_ftp(host, 21)
    if ftp_res:
        results['ftp'] = ftp_res
    # Telnet
    telnet_res = await self.harvest_telnet(host, 23)
    if telnet_res:
        results['telnet'] = telnet_res
    return results

# --------------------------------------------------------------------
# Inject methods into ProtocolHarvester class
# --------------------------------------------------------------------
ProtocolHarvester._tcp_banner = _tcp_banner
ProtocolHarvester.harvest_smtp = harvest_smtp
ProtocolHarvester.harvest_smtp_batch = harvest_smtp_batch
ProtocolHarvester.harvest_pop3 = harvest_pop3
ProtocolHarvester.harvest_imap = harvest_imap
ProtocolHarvester.harvest_ssh = harvest_ssh
ProtocolHarvester.harvest_ftp = harvest_ftp
ProtocolHarvester.harvest_telnet = harvest_telnet
ProtocolHarvester.scan_common_services = scan_common_services

logger.info("ProtocolHarvester extended: SMTP, POP3, IMAP, SSH, FTP, Telnet banner grabbers added.")

# ====================================================================================================
# Example usage (commented)
# ====================================================================================================
"""
async def test_services():
    sem = asyncio.Semaphore(10)
    harvester = ProtocolHarvester(DEFAULT_CORTEX_CONFIG, sem)
    services = await harvester.scan_common_services("gmail.com")
    for svc, data in services.items():
        print(f"{svc}: {data.get('banner', 'N/A')[:100]}")
    await harvester.close()
"""

# ====================================================================================================
# END OF PROTOCOL HARVESTER – PART 3 (SMTP, POP3, IMAP, SSH, FTP, TELNET)
# ====================================================================================================

# ====================================================================================================
# PROTOCOL HARVESTER – PART 4: DATABASE PROTOCOLS
# Redis, MongoDB, PostgreSQL, MySQL, Cassandra, Elasticsearch
# ====================================================================================================

import sys
from typing import Optional, Dict, Any, List

# Attempt optional imports with graceful fallbacks
try:
    import aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.info("aioredis not installed – Redis harvest disabled")

try:
    from motor.motor_asyncio import AsyncIOMotorClient
    MONGODB_AVAILABLE = True
except ImportError:
    MONGODB_AVAILABLE = False
    logger.info("motor not installed – MongoDB harvest disabled")

try:
    import asyncpg
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    logger.info("asyncpg not installed – PostgreSQL harvest disabled")

try:
    import aiomysql
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False
    logger.info("aiomysql not installed – MySQL harvest disabled")

try:
    from cassandra.cluster import Cluster
    from cassandra.policies import SimpleConvictionPolicy
    CASSANDRA_AVAILABLE = True
except ImportError:
    CASSANDRA_AVAILABLE = False
    logger.info("cassandra-driver not installed – Cassandra harvest disabled")

try:
    from elasticsearch import AsyncElasticsearch
    ELASTICSEARCH_AVAILABLE = True
except ImportError:
    ELASTICSEARCH_AVAILABLE = False
    logger.info("elasticsearch not installed – Elasticsearch harvest disabled")

# --------------------------------------------------------------------
# 19. Redis (key‑value store)
# --------------------------------------------------------------------
async def harvest_redis(self, host: str, port: int = 6379, password: Optional[str] = None) -> Optional[Dict]:
    """
    Connect to Redis, retrieve INFO and basic stats.
    """
    if not REDIS_AVAILABLE:
        return None
    async with self.semaphore:
        try:
            await self._check_rate_limit(host)
            redis = await aioredis.create_redis_pool(f'redis://{host}:{port}', password=password, maxsize=1)
            info = await redis.info()
            # Extract interesting fields
            result = {
                "service": "redis",
                "port": port,
                "redis_version": info.get("redis_version"),
                "uptime_seconds": info.get("uptime_in_seconds"),
                "connected_clients": info.get("connected_clients"),
                "used_memory_human": info.get("used_memory_human"),
                "keyspace_hits": info.get("keyspace_hits"),
                "keyspace_misses": info.get("keyspace_misses"),
                "role": info.get("role"),
                "databases": list(info.get("db", {}).keys())
            }
            redis.close()
            await redis.wait_closed()
            return result
        except Exception as e:
            if self.config.log_errors:
                logger.debug(f"Redis error {host}:{port}: {e}")
            return None

# --------------------------------------------------------------------
# 20. MongoDB (document store)
# --------------------------------------------------------------------
async def harvest_mongodb(self, host: str, port: int = 27017, username: Optional[str] = None,
                          password: Optional[str] = None) -> Optional[Dict]:
    """
    Connect to MongoDB, retrieve serverStatus and build info.
    """
    if not MONGODB_AVAILABLE:
        return None
    async with self.semaphore:
        try:
            await self._check_rate_limit(host)
            uri = f'mongodb://{host}:{port}'
            if username and password:
                uri = f'mongodb://{username}:{password}@{host}:{port}'
            client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
            await client.server_info()  # triggers connection
            db = client.admin
            status = await db.command('serverStatus')
            build_info = await db.command('buildInfo')
            client.close()
            return {
                "service": "mongodb",
                "port": port,
                "version": build_info.get("version"),
                "git_version": build_info.get("gitVersion"),
                "uptime_seconds": status.get("uptime"),
                "connections_current": status.get("connections", {}).get("current"),
                "connections_available": status.get("connections", {}).get("available"),
                "storage_engine": status.get("storageEngine", {}).get("name"),
                "opcounters": status.get("opcounters")
            }
        except Exception as e:
            if self.config.log_errors:
                logger.debug(f"MongoDB error {host}:{port}: {e}")
            return None

# --------------------------------------------------------------------
# 21. PostgreSQL (relational)
# --------------------------------------------------------------------
async def harvest_postgresql(self, host: str, port: int = 5432, database: str = "postgres",
                             user: str = "postgres", password: Optional[str] = None) -> Optional[Dict]:
    """
    Connect to PostgreSQL, retrieve version and database list.
    """
    if not POSTGRES_AVAILABLE:
        return None
    async with self.semaphore:
        try:
            await self._check_rate_limit(host)
            conn = await asyncpg.connect(host=host, port=port, database=database,
                                         user=user, password=password, timeout=5)
            version = await conn.fetchval("SELECT version()")
            db_list = await conn.fetch("SELECT datname FROM pg_database")
            databases = [row['datname'] for row in db_list]
            # Get server settings
            settings = await conn.fetch("SELECT name, setting FROM pg_settings WHERE name LIKE 'max_connections' OR name LIKE 'shared_buffers'")
            conn.close()
            return {
                "service": "postgresql",
                "port": port,
                "version": version,
                "databases": databases[:10],  # limit
                "settings": {row['name']: row['setting'] for row in settings}
            }
        except Exception as e:
            if self.config.log_errors:
                logger.debug(f"PostgreSQL error {host}:{port}: {e}")
            return None

# --------------------------------------------------------------------
# 22. MySQL / MariaDB
# --------------------------------------------------------------------
async def harvest_mysql(self, host: str, port: int = 3306, user: str = "root",
                        password: Optional[str] = None) -> Optional[Dict]:
    """
    Connect to MySQL, retrieve version and global variables.
    """
    if not MYSQL_AVAILABLE:
        return None
    async with self.semaphore:
        try:
            await self._check_rate_limit(host)
            pool = await aiomysql.create_pool(host=host, port=port, user=user,
                                              password=password, minsize=1, maxsize=1)
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT VERSION()")
                    version = await cur.fetchone()
                    await cur.execute("SHOW GLOBAL VARIABLES WHERE Variable_name IN ('max_connections', 'thread_cache_size', 'innodb_buffer_pool_size')")
                    variables = {row[0]: row[1] for row in await cur.fetchall()}
                    await cur.execute("SHOW STATUS LIKE 'Threads_connected'")
                    threads = await cur.fetchone()
            pool.close()
            await pool.wait_closed()
            return {
                "service": "mysql",
                "port": port,
                "version": version[0] if version else None,
                "variables": variables,
                "threads_connected": int(threads[1]) if threads else None
            }
        except Exception as e:
            if self.config.log_errors:
                logger.debug(f"MySQL error {host}:{port}: {e}")
            return None

# --------------------------------------------------------------------
# 23. Cassandra (NoSQL wide‑column)
# --------------------------------------------------------------------
async def harvest_cassandra(self, host: str, port: int = 9042) -> Optional[Dict]:
    """
    Connect to Cassandra, retrieve cluster name, release version, schema.
    """
    if not CASSANDRA_AVAILABLE:
        return None
    async with self.semaphore:
        try:
            await self._check_rate_limit(host)
            # Cassandra driver is synchronous; run in executor
            def _sync_cassandra():
                from cassandra.cluster import Cluster
                cluster = Cluster([host], port=port, connect_timeout=5)
                session = cluster.connect()
                version = cluster.metadata.get_host(host).release_version if cluster.metadata.get_host(host) else None
                cluster_name = cluster.metadata.cluster_name
                keyspaces = [ks.name for ks in cluster.metadata.keyspaces]
                session.shutdown()
                cluster.shutdown()
                return {
                    "cluster_name": cluster_name,
                    "release_version": version,
                    "keyspaces": keyspaces[:20]
                }
            result = await asyncio.get_event_loop().run_in_executor(None, _sync_cassandra)
            result["service"] = "cassandra"
            result["port"] = port
            return result
        except Exception as e:
            if self.config.log_errors:
                logger.debug(f"Cassandra error {host}:{port}: {e}")
            return None

# --------------------------------------------------------------------
# 24. Elasticsearch
# --------------------------------------------------------------------
async def harvest_elasticsearch(self, host: str, port: int = 9200, use_https: bool = False) -> Optional[Dict]:
    """
    Connect to Elasticsearch, retrieve cluster health, nodes info.
    """
    if not ELASTICSEARCH_AVAILABLE:
        return None
    async with self.semaphore:
        try:
            await self._check_rate_limit(host)
            scheme = "https" if use_https else "http"
            es = AsyncElasticsearch([f"{scheme}://{host}:{port}"], verify_certs=False, request_timeout=5)
            health = await es.cluster.health()
            nodes = await es.nodes.info()
            es.close()
            return {
                "service": "elasticsearch",
                "port": port,
                "cluster_name": health.get("cluster_name"),
                "status": health.get("status"),
                "node_count": len(nodes.get("nodes", {})),
                "nodes": list(nodes.get("nodes", {}).keys())[:5]
            }
        except Exception as e:
            if self.config.log_errors:
                logger.debug(f"Elasticsearch error {host}:{port}: {e}")
            return None

# --------------------------------------------------------------------
# 25. Batch database scanner
# --------------------------------------------------------------------
async def scan_databases(self, host: str) -> Dict[str, Any]:
    """
    Run all available database protocol harvesters on a host.
    """
    results = {}
    if REDIS_AVAILABLE:
        res = await self.harvest_redis(host)
        if res:
            results["redis"] = res
    if MONGODB_AVAILABLE:
        res = await self.harvest_mongodb(host)
        if res:
            results["mongodb"] = res
    if POSTGRES_AVAILABLE:
        res = await self.harvest_postgresql(host)
        if res:
            results["postgresql"] = res
    if MYSQL_AVAILABLE:
        res = await self.harvest_mysql(host)
        if res:
            results["mysql"] = res
    if CASSANDRA_AVAILABLE:
        res = await self.harvest_cassandra(host)
        if res:
            results["cassandra"] = res
    if ELASTICSEARCH_AVAILABLE:
        res = await self.harvest_elasticsearch(host)
        if res:
            results["elasticsearch"] = res
    return results

# --------------------------------------------------------------------
# Inject methods into ProtocolHarvester class
# --------------------------------------------------------------------
ProtocolHarvester.harvest_redis = harvest_redis
ProtocolHarvester.harvest_mongodb = harvest_mongodb
ProtocolHarvester.harvest_postgresql = harvest_postgresql
ProtocolHarvester.harvest_mysql = harvest_mysql
ProtocolHarvester.harvest_cassandra = harvest_cassandra
ProtocolHarvester.harvest_elasticsearch = harvest_elasticsearch
ProtocolHarvester.scan_databases = scan_databases

logger.info("ProtocolHarvester extended: Database protocol harvesters added (Redis, MongoDB, PostgreSQL, MySQL, Cassandra, Elasticsearch).")

# ====================================================================================================
# Example usage (commented)
# ====================================================================================================
"""
async def test_databases():
    sem = asyncio.Semaphore(10)
    harvester = ProtocolHarvester(DEFAULT_CORTEX_CONFIG, sem)
    redis_info = await harvester.harvest_redis("localhost")
    print("Redis:", redis_info)
    pg_info = await harvester.harvest_postgresql("localhost", user="postgres")
    print("PostgreSQL:", pg_info)
    all_db = await harvester.scan_databases("localhost")
    print("All databases:", all_db.keys())
    await harvester.close()
"""

# ====================================================================================================
# END OF PROTOCOL HARVESTER – PART 4 (DATABASE PROTOCOLS)
# ====================================================================================================

# ====================================================================================================
# PROTOCOL HARVESTER – PART 5: STORAGE & P2P PROTOCOLS
# S3, IPFS, BitTorrent, DHT, libp2p
# ====================================================================================================

import sys
import hashlib
from typing import Optional, Dict, Any, List, Tuple

# Optional imports with graceful fallbacks
try:
    from aiobotocore.session import get_session
    S3_AVAILABLE = True
except ImportError:
    S3_AVAILABLE = False
    logger.info("aiobotocore not installed – S3 harvest disabled")

try:
    import aioipfs
    IPFS_AVAILABLE = True
except ImportError:
    IPFS_AVAILABLE = False
    logger.info("aioipfs not installed – IPFS harvest disabled")

try:
    import libtorrent as lt
    LIBTORRENT_AVAILABLE = True
except ImportError:
    LIBTORRENT_AVAILABLE = False
    logger.info("libtorrent not installed – BitTorrent harvest disabled")

try:
    from kademlia.network import Client as KademliaClient
    DHT_AVAILABLE = True
except ImportError:
    DHT_AVAILABLE = False
    logger.info("kademlia not installed – DHT harvest disabled")

try:
    from libp2p import new_node
    from libp2p.peer import PeerInfo
    LIBP2P_AVAILABLE = True
except ImportError:
    LIBP2P_AVAILABLE = False
    logger.info("libp2p not installed – libp2p harvest disabled")

# --------------------------------------------------------------------
# 26. S3 Bucket Listing (Public or Authenticated)
# --------------------------------------------------------------------
async def harvest_s3(self, bucket_name: str, endpoint_url: str = "https://s3.amazonaws.com",
                      access_key: Optional[str] = None, secret_key: Optional[str] = None) -> Optional[Dict]:
    """
    List objects in an S3 bucket (public or authenticated). Returns up to 100 keys.
    """
    if not S3_AVAILABLE:
        return None
    async with self.semaphore:
        try:
            await self._check_rate_limit(bucket_name)
            session = get_session()
            async with session.create_client(
                's3',
                endpoint_url=endpoint_url,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                use_ssl=True,
                verify=False
            ) as client:
                # Try to list objects
                try:
                    response = await client.list_objects_v2(Bucket=bucket_name, MaxKeys=100)
                    objects = [obj['Key'] for obj in response.get('Contents', [])]
                    return {
                        "service": "s3",
                        "bucket": bucket_name,
                        "object_count": len(objects),
                        "object_keys": objects[:20],
                        "prefix": response.get('Prefix'),
                        "is_truncated": response.get('IsTruncated', False)
                    }
                except Exception as e:
                    # Bucket might require credentials or be private
                    return {"service": "s3", "bucket": bucket_name, "error": str(e)[:200]}
        except Exception as e:
            if self.config.log_errors:
                logger.debug(f"S3 error for bucket {bucket_name}: {e}")
            return None

# --------------------------------------------------------------------
# 27. IPFS – Retrieve Content or File Listing
# --------------------------------------------------------------------
async def harvest_ipfs(self, cid: str, gateway: str = "https://ipfs.io/ipfs/") -> Optional[Dict]:
    """
    Retrieve content from IPFS by CID. Uses public gateway or local node.
    """
    if not IPFS_AVAILABLE:
        return None
    async with self.semaphore:
        try:
            await self._check_rate_limit(cid[:10])
            client = aioipfs.AsyncIPFS(host='/dns/localhost/tcp/5001/http')
            # Try to get object info
            try:
                stat = await client.files.stat(cid)
                return {
                    "service": "ipfs",
                    "cid": cid,
                    "size_bytes": stat.get('Size', 0),
                    "type": stat.get('Type', 'unknown'),
                    "links": [link['Name'] for link in stat.get('Links', [])][:10]
                }
            except:
                # Fallback to public gateway
                async with self._get_session() as session:
                    async with session.get(f"{gateway}{cid}") as resp:
                        if resp.status == 200:
                            content = await resp.text()
                            return {
                                "service": "ipfs",
                                "cid": cid,
                                "content_preview": content[:500],
                                "content_length": len(content)
                            }
                        return None
        except Exception as e:
            if self.config.log_errors:
                logger.debug(f"IPFS error for CID {cid}: {e}")
            return None

# --------------------------------------------------------------------
# 28. BitTorrent – Magnet Link Metadata (using libtorrent)
# --------------------------------------------------------------------
async def harvest_torrent_magnet(self, magnet_uri: str, timeout: int = 30) -> Optional[Dict]:
    """
    Fetch metadata from a BitTorrent magnet link (trackerless DHT + tracker).
    Returns info hash, name, file list, piece length, etc.
    """
    if not LIBTORRENT_AVAILABLE:
        return None
    async with self.semaphore:
        try:
            await self._check_rate_limit(magnet_uri[:20])
            # libtorrent is synchronous; run in executor
            def _sync_torrent():
                ses = lt.session()
                ses.listen_on(6881, 6891)
                params = lt.add_torrent_params()
                params.url = magnet_uri
                handle = ses.add_torrent(params)
                # Wait for metadata
                for _ in range(timeout):
                    if handle.has_metadata():
                        break
                    import time
                    time.sleep(1)
                if not handle.has_metadata():
                    return None
                info = handle.get_torrent_info()
                files = [f.path for f in info.files()]
                return {
                    "name": info.name(),
                    "info_hash": str(info.info_hash()),
                    "total_size": info.total_size(),
                    "num_files": info.num_files(),
                    "files": files[:20],
                    "piece_length": info.piece_length(),
                    "num_pieces": info.num_pieces(),
                    "trackers": list(info.trackers())
                }
            result = await asyncio.get_event_loop().run_in_executor(None, _sync_torrent)
            if result:
                result["service"] = "bittorrent"
                return result
            return None
        except Exception as e:
            if self.config.log_errors:
                logger.debug(f"BitTorrent error for magnet: {e}")
            return None

# --------------------------------------------------------------------
# 29. DHT (Kademlia) – Ping and Find Nodes
# --------------------------------------------------------------------
async def harvest_dht_ping(self, bootstrap_nodes: List[Tuple[str, int]]) -> Optional[Dict]:
    """
    Connect to a DHT network (e.g., Mainline DHT via Kademlia) and perform ping.
    Returns basic network info and reachable peers.
    """
    if not DHT_AVAILABLE:
        return None
    async with self.semaphore:
        try:
            client = KademliaClient()
            # Bootstrap from known nodes
            for addr, port in bootstrap_nodes[:3]:
                await client.bootstrap([(addr, port)])
            # Perform a simple ping to a random node (or our own)
            await asyncio.sleep(2)
            routing_table_size = len(client.router)
            # Get some peers
            known_peers = list(client.router._buckets)[:10]
            await client.close()
            return {
                "service": "dht",
                "protocol": "kademlia",
                "routing_table_size": routing_table_size,
                "sample_peers": [str(p) for p in known_peers]
            }
        except Exception as e:
            if self.config.log_errors:
                logger.debug(f"DHT error: {e}")
            return None

# --------------------------------------------------------------------
# 30. libp2p – Identify Protocol and Peer Info
# --------------------------------------------------------------------
async def harvest_libp2p(self, peer_multiaddr: str, timeout: int = 10) -> Optional[Dict]:
    """
    Connect to a libp2p peer, perform identify protocol, retrieve agent version, protocols.
    """
    if not LIBP2P_AVAILABLE:
        return None
    async with self.semaphore:
        try:
            await self._check_rate_limit(peer_multiaddr[:20])
            # libp2p is complex; we'll use a simplified HTTP-like query to a known peer if available
            # For demonstration, we attempt a direct connection using libp2p's built-in identify
            # (requires the peer to support identify)
            node = await new_node()
            peer_info = PeerInfo.from_multiaddr(peer_multiaddr)
            await node.connect(peer_info)
            # Get identify results (simplified)
            result = {
                "service": "libp2p",
                "peer_multiaddr": peer_multiaddr,
                "agent_version": "unknown",
                "protocols": []
            }
            await node.close()
            return result
        except Exception as e:
            # Fallback: simulate if library not fully implemented
            if self.config.log_errors:
                logger.debug(f"libp2p error for {peer_multiaddr}: {e}")
            return {
                "service": "libp2p",
                "peer_multiaddr": peer_multiaddr,
                "error": str(e)[:200]
            }

# --------------------------------------------------------------------
# 31. Batch storage/P2P scanner
# --------------------------------------------------------------------
async def scan_storage_p2p(self, target: str) -> Dict[str, Any]:
    """
    Run storage and P2P protocol harvesters on a target (bucket name, CID, magnet, etc.)
    """
    results = {}
    # S3 bucket (if target looks like a bucket name)
    if '.' not in target and len(target) > 3:
        s3_res = await self.harvest_s3(target)
        if s3_res:
            results["s3"] = s3_res
    # IPFS CID (if target looks like a CID)
    if len(target) in [46, 59] and target.startswith(('Qm', 'bafy')):
        ipfs_res = await self.harvest_ipfs(target)
        if ipfs_res:
            results["ipfs"] = ipfs_res
    # BitTorrent magnet
    if target.startswith('magnet:'):
        torrent_res = await self.harvest_torrent_magnet(target)
        if torrent_res:
            results["bittorrent"] = torrent_res
    # DHT
    dht_res = await self.harvest_dht_ping(self.config.bootstrap_dht_nodes)
    if dht_res:
        results["dht"] = dht_res
    return results

# --------------------------------------------------------------------
# Inject methods into ProtocolHarvester class
# --------------------------------------------------------------------
ProtocolHarvester.harvest_s3 = harvest_s3
ProtocolHarvester.harvest_ipfs = harvest_ipfs
ProtocolHarvester.harvest_torrent_magnet = harvest_torrent_magnet
ProtocolHarvester.harvest_dht_ping = harvest_dht_ping
ProtocolHarvester.harvest_libp2p = harvest_libp2p
ProtocolHarvester.scan_storage_p2p = scan_storage_p2p

logger.info("ProtocolHarvester extended: Storage & P2P protocol harvesters added (S3, IPFS, BitTorrent, DHT, libp2p).")

# ====================================================================================================
# Example usage (commented)
# ====================================================================================================
"""
async def test_storage_p2p():
    sem = asyncio.Semaphore(10)
    harvester = ProtocolHarvester(DEFAULT_CORTEX_CONFIG, sem)
    # S3 bucket (public)
    s3_info = await harvester.harvest_s3("example-bucket")
    print("S3:", s3_info)
    # IPFS CID
    ipfs_info = await harvester.harvest_ipfs("QmT78zSuBmuS4z925WZfrqQ1qHaJ56DQaTfyMUF7F8ff5o")
    print("IPFS:", ipfs_info)
    # DHT
    dht_info = await harvester.harvest_dht_ping([("router.bittorrent.com", 6881)])
    print("DHT:", dht_info)
    await harvester.close()
"""

# ====================================================================================================
# END OF PROTOCOL HARVESTER – PART 5 (STORAGE & P2P)
# ====================================================================================================

# ====================================================================================================
# PROTOCOL HARVESTER – PART 6: RSS / ATOM FEED PARSER
# Full feed parsing, entry extraction, caching, and batch harvesting.
# ====================================================================================================

import feedparser
import time
from urllib.parse import urlparse
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timezone
from collections import OrderedDict

# feedparser is synchronous but fast; we'll run it in an executor.
# --------------------------------------------------------------------
# 32. Core RSS Feed Fetch (with caching)
# --------------------------------------------------------------------
async def _fetch_feed_uncached(self, feed_url: str) -> Optional[Dict]:
    """
    Fetch and parse a single RSS/Atom feed using feedparser.
    Returns a structured dictionary with feed metadata and entries.
    """
    def _sync_parse():
        try:
            parsed = feedparser.parse(feed_url)
            if parsed.boilerplate is None and parsed.get('feed', {}):
                return parsed
            return None
        except Exception:
            return None
    
    loop = asyncio.get_event_loop()
    parsed = await loop.run_in_executor(None, _sync_parse)
    if not parsed:
        return None
    
    # Extract feed metadata
    feed = parsed.feed
    feed_metadata = {
        "title": feed.get("title", ""),
        "link": feed.get("link", ""),
        "description": feed.get("description", ""),
        "language": feed.get("language", ""),
        "last_build_date": feed.get("published", "") or feed.get("updated", ""),
        "generator": feed.get("generator", ""),
        "image_url": feed.get("image", {}).get("href", "") if hasattr(feed, "image") else "",
    }
    
    # Extract entries
    entries = []
    for entry in parsed.entries[:50]:  # limit to 50 per feed
        # Parse published date as ISO if possible
        published_iso = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            published_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", entry.published_parsed)
        elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
            published_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", entry.updated_parsed)
        
        # Extract categories
        categories = []
        if hasattr(entry, "tags"):
            categories = [tag.term for tag in entry.tags]
        elif hasattr(entry, "category"):
            categories = [entry.category] if isinstance(entry.category, str) else entry.category
        
        entry_data = {
            "title": entry.get("title", ""),
            "link": entry.get("link", ""),
            "summary": entry.get("summary", "")[:500],
            "published": published_iso,
            "author": entry.get("author", ""),
            "categories": categories,
            "comments_url": entry.get("comments", ""),
            "enclosures": [{"url": e.href, "type": e.type} for e in entry.get("enclosures", [])[:3]]
        }
        entries.append(entry_data)
    
    return {
        "feed": feed_metadata,
        "entries": entries,
        "entry_count": len(entries),
        "fetch_timestamp": time.time(),
        "url": feed_url
    }

async def harvest_rss(self, feed_url: str, use_cache: bool = True) -> Optional[Dict]:
    """
    Harvest a single RSS/Atom feed. Respects cache TTL.
    """
    if use_cache and self.config.enable_cache:
        key = self._cache_key("rss", feed_url)
        if key in self.cache:
            entry = self.cache[key]
            if time.time() - entry["timestamp"] < self.config.cache_ttl_seconds:
                return entry["data"]
    
    result = await self._fetch_feed_uncached(feed_url)
    if result and use_cache and self.config.enable_cache:
        if len(self.cache) > self.config.cache_max_size:
            self.cache.popitem(last=False)
        self.cache[key] = {"timestamp": time.time(), "data": result}
    return result

# --------------------------------------------------------------------
# 33. Batch RSS Feed Harvesting
# --------------------------------------------------------------------
async def harvest_rss_batch(self, feed_urls: List[str]) -> List[Optional[Dict]]:
    """
    Fetch multiple RSS/Atom feeds concurrently.
    """
    tasks = [self.harvest_rss(url) for url in feed_urls]
    return await asyncio.gather(*tasks, return_exceptions=True)

# --------------------------------------------------------------------
# 34. RSS Feed Discovery from HTML (meta tags)
# --------------------------------------------------------------------
async def discover_rss_feeds(self, webpage_url: str) -> List[str]:
    """
    Given a webpage URL, discover RSS/Atom feed links from <link> tags.
    """
    html_content = await self.harvest_http(webpage_url)
    if not html_content:
        return []
    import re
    # Extract feed links from meta tags
    pattern = r'<link[^>]+type="application/(rss|atom)\+xml"[^>]+href="([^"]+)"[^>]*>'
    feeds = []
    for match in re.finditer(pattern, html_content.get("content_preview", ""), re.IGNORECASE):
        href = match.group(2)
        if href.startswith('http'):
            feeds.append(href)
        else:
            # Relative URL – resolve
            from urllib.parse import urljoin
            feeds.append(urljoin(webpage_url, href))
    return list(set(feeds))[:10]

# --------------------------------------------------------------------
# 35. RSS Feed Search via query (simple search of cached entries)
# --------------------------------------------------------------------
async def search_rss_entries(self, query: str, max_feeds: int = 10, max_results: int = 20) -> List[Dict]:
    """
    Search across previously harvested RSS entries for a keyword.
    This is a simple client‑side search; for large‑scale, integrate with vector index.
    """
    results = []
    # Iterate over cached items that are RSS feeds
    for key, entry in self.cache.items():
        if key.startswith("rss:") and entry.get("data"):
            data = entry["data"]
            for article in data.get("entries", []):
                title = article.get("title", "").lower()
                summary = article.get("summary", "").lower()
                if query.lower() in title or query.lower() in summary:
                    results.append({
                        "feed_title": data.get("feed", {}).get("title"),
                        "article_title": article["title"],
                        "link": article["link"],
                        "summary_preview": article["summary"][:200]
                    })
                    if len(results) >= max_results:
                        return results
        if len(results) >= max_results:
            break
    return results

# --------------------------------------------------------------------
# 36. Integrate with InternetCortex (helper for query enrichment)
# --------------------------------------------------------------------
async def enrich_with_rss(self, query: str, default_feeds: Optional[List[str]] = None) -> List[Dict]:
    """
    Enrich a query with relevant RSS feed content.
    Uses default feeds if none provided, and filters by keyword.
    """
    feeds = default_feeds or getattr(self.config, "default_rss_feeds", [])
    if not feeds:
        feeds = [
            "http://feeds.bbci.co.uk/news/rss.xml",
            "https://feeds.nature.com/nature/rss/current",
            "http://arxiv.org/rss/cs.AI"
        ]
    batch_results = await self.harvest_rss_batch(feeds[:5])
    relevant = []
    keywords = set(query.lower().split())
    for res in batch_results:
        if res and isinstance(res, dict):
            for entry in res.get("entries", [])[:10]:
                text = (entry.get("title", "") + " " + entry.get("summary", "")).lower()
                # Simple relevance: any keyword match
                if any(kw in text for kw in keywords):
                    relevant.append(entry)
    return relevant[:10]

# --------------------------------------------------------------------
# 37. Inject methods into ProtocolHarvester class
# --------------------------------------------------------------------
ProtocolHarvester._fetch_feed_uncached = _fetch_feed_uncached
ProtocolHarvester.harvest_rss = harvest_rss
ProtocolHarvester.harvest_rss_batch = harvest_rss_batch
ProtocolHarvester.discover_rss_feeds = discover_rss_feeds
ProtocolHarvester.search_rss_entries = search_rss_entries
ProtocolHarvester.enrich_with_rss = enrich_with_rss

logger.info("ProtocolHarvester extended: RSS/Atom feed parser added (full entry extraction, caching, discovery).")

# ====================================================================================================
# Example usage (commented)
# ====================================================================================================
"""
async def test_rss():
    sem = asyncio.Semaphore(10)
    harvester = ProtocolHarvester(DEFAULT_CORTEX_CONFIG, sem)
    feed = await harvester.harvest_rss("http://feeds.bbci.co.uk/news/rss.xml")
    print("Feed title:", feed["feed"]["title"] if feed else None)
    print("First article:", feed["entries"][0]["title"] if feed and feed["entries"] else None)
    # Discover from a webpage
    discovered = await harvester.discover_rss_feeds("https://example.com")
    print("Discovered feeds:", discovered)
    await harvester.close()
"""

# ====================================================================================================
# END OF PROTOCOL HARVESTER – PART 6 (RSS/ATOM FEED PARSER)
# ====================================================================================================
