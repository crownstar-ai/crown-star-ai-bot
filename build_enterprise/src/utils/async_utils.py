# ====================================================================================================
# async_utils.py – Asynchronous utilities for CrownStar‑Absolute
# Features:
#   - Retry decorator with exponential backoff (asyncio)
#   - Timeout context manager and function wrapper
#   - Batch processor for chunked async operations
#   - Async map with concurrency control
#   - Rate limiter (token bucket and sliding window)
#   - Throttled asyncio.gather
#   - Async task pool and worker queue
#   - Debounce and throttle decorators
#   - Background task manager
# ====================================================================================================

import asyncio
import time
import random
import functools
from typing import List, Callable, TypeVar, Awaitable, Optional, Any, Dict, Union, Iterator, Tuple
from collections import deque
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')

# --------------------------------------------------------------------
# 1. Retry with Exponential Backoff
# --------------------------------------------------------------------

def async_retry(max_retries: int = 3, 
                initial_delay: float = 1.0,
                backoff_factor: float = 2.0,
                exceptions: tuple = (Exception,),
                on_retry: Optional[Callable[[Exception, int, float], None]] = None):
    """
    Decorator for async functions that retries on failure.
    
    Args:
        max_retries: Maximum number of retry attempts (excluding first try)
        initial_delay: Delay before first retry (seconds)
        backoff_factor: Multiplier for subsequent delays
        exceptions: Tuple of exception types to catch and retry
        on_retry: Optional callback called on each retry (exception, attempt, delay)
    
    Example:
        @async_retry(max_retries=3)
        async def fetch_data():
            return await some_unreliable_api()
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None
            delay = initial_delay
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        break
                    if on_retry:
                        on_retry(e, attempt + 1, delay)
                    else:
                        logger.warning(f"Retry {attempt+1}/{max_retries} for {func.__name__}: {e}")
                    await asyncio.sleep(delay)
                    delay *= backoff_factor
            raise last_exception
        return wrapper
    return decorator

async def retry_async(func: Callable[..., Awaitable[T]], 
                      *args, 
                      max_retries: int = 3,
                      initial_delay: float = 1.0,
                      backoff_factor: float = 2.0,
                      **kwargs) -> T:
    """
    Retry an async function call without decorator syntax.
    
    Example:
        result = await retry_async(unreliable_api, arg1, arg2, max_retries=5)
    """
    delay = initial_delay
    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if attempt == max_retries:
                break
            logger.warning(f"Retry {attempt+1}/{max_retries}: {e}")
            await asyncio.sleep(delay)
            delay *= backoff_factor
    raise last_exception

# --------------------------------------------------------------------
# 2. Timeout Utilities
# --------------------------------------------------------------------

async def timeout(awaitable: Awaitable[T], timeout_seconds: float, 
                  fallback: Optional[T] = None, 
                  raise_on_timeout: bool = True) -> Optional[T]:
    """
    Execute an awaitable with a timeout.
    
    Args:
        awaitable: Coroutine or awaitable object
        timeout_seconds: Timeout in seconds
        fallback: Value to return on timeout (if raise_on_timeout is False)
        raise_on_timeout: If True, raises asyncio.TimeoutError; else returns fallback
    
    Returns:
        Result of awaitable or fallback on timeout
    
    Raises:
        asyncio.TimeoutError if raise_on_timeout is True and timeout occurs
    """
    try:
        return await asyncio.wait_for(awaitable, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        if raise_on_timeout:
            raise
        logger.warning(f"Timeout after {timeout_seconds}s")
        return fallback

@asynccontextmanager
async def timeout_context(timeout_seconds: float):
    """
    Context manager for timeouts.
    
    Example:
        async with timeout_context(5.0):
            await some_slow_operation()
    """
    try:
        await asyncio.wait_for(asyncio.sleep(0), timeout=timeout_seconds)
        yield
    except asyncio.TimeoutError:
        raise TimeoutError(f"Operation timed out after {timeout_seconds}s")

def with_timeout(timeout_seconds: float):
    """
    Decorator that adds timeout to async function.
    
    Example:
        @with_timeout(5.0)
        async def slow_func():
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout_seconds)
        return wrapper
    return decorator

# --------------------------------------------------------------------
# 3. Batch Processor
# --------------------------------------------------------------------

class BatchProcessor:
    """
    Process items in batches with async function.
    
    Example:
        processor = BatchProcessor(batch_size=100, concurrency=5)
        results = await processor.process(items, process_func)
    """
    
    def __init__(self, batch_size: int = 100, concurrency: int = 5):
        self.batch_size = batch_size
        self.concurrency = concurrency
        self.semaphore = asyncio.Semaphore(concurrency)
    
    async def process(self, items: List[T], 
                      process_func: Callable[[List[T]], Awaitable[List[Any]]],
                      progress_callback: Optional[Callable[[int, int], None]] = None) -> List[Any]:
        """
        Process items in batches.
        
        Args:
            items: List of items to process
            process_func: Async function that takes a batch and returns results
            progress_callback: Optional callback(total_processed, total_items)
        
        Returns:
            Flattened list of results from all batches
        """
        results = []
        total = len(items)
        
        async def process_batch(batch_idx: int, batch: List[T]) -> List[Any]:
            async with self.semaphore:
                batch_results = await process_func(batch)
                if progress_callback:
                    progress_callback((batch_idx + 1) * self.batch_size, total)
                return batch_results
        
        batches = [items[i:i+self.batch_size] for i in range(0, total, self.batch_size)]
        tasks = [process_batch(i, batch) for i, batch in enumerate(batches)]
        
        batch_results = await asyncio.gather(*tasks)
        for br in batch_results:
            results.extend(br)
        
        return results

def chunked(items: List[T], chunk_size: int) -> Iterator[List[T]]:
    """Yield successive chunks of items."""
    for i in range(0, len(items), chunk_size):
        yield items[i:i+chunk_size]

async def batch_map(func: Callable[[T], Awaitable[Any]], 
                    items: List[T], 
                    concurrency: int = 10) -> List[Any]:
    """
    Apply async function to each item with concurrency limit.
    
    Example:
        results = await batch_map(fetch_url, urls, concurrency=20)
    """
    semaphore = asyncio.Semaphore(concurrency)
    
    async def bounded_apply(item: T) -> Any:
        async with semaphore:
            return await func(item)
    
    return await asyncio.gather(*[bounded_apply(item) for item in items])

# --------------------------------------------------------------------
# 4. Rate Limiter
# --------------------------------------------------------------------

class RateLimiter:
    """
    Token bucket rate limiter for async operations.
    
    Example:
        limiter = RateLimiter(max_calls=10, period=1.0)
        async with limiter:
            await make_request()
    """
    
    def __init__(self, max_calls: int, period: float = 1.0):
        self.max_calls = max_calls
        self.period = period
        self.tokens = max_calls
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """Acquire a token, waiting if necessary."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(self.max_calls, self.tokens + elapsed * (self.max_calls / self.period))
            self.last_refill = now
            
            if self.tokens >= 1:
                self.tokens -= 1
                return
            
            # Wait for next token
            wait_time = (1 - self.tokens) * (self.period / self.max_calls)
            await asyncio.sleep(wait_time)
            self.tokens = 0
            self.last_refill = time.monotonic()
    
    async def __aenter__(self):
        await self.acquire()
        return self
    
    async def __aexit__(self, *args):
        pass

class SlidingWindowRateLimiter:
    """
    Sliding window rate limiter (more accurate than token bucket).
    
    Example:
        limiter = SlidingWindowRateLimiter(max_calls=100, window_seconds=60)
    """
    
    def __init__(self, max_calls: int, window_seconds: int = 60):
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._timestamps: deque = deque()
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            # Remove timestamps outside the window
            while self._timestamps and self._timestamps[0] < now - self.window_seconds:
                self._timestamps.popleft()
            
            if len(self._timestamps) < self.max_calls:
                self._timestamps.append(now)
                return
            
            # Wait until oldest timestamp expires
            wait_time = self._timestamps[0] - (now - self.window_seconds)
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            self._timestamps.popleft()
            self._timestamps.append(time.monotonic())
    
    async def __aenter__(self):
        await self.acquire()
        return self
    
    async def __aexit__(self, *args):
        pass

# --------------------------------------------------------------------
# 5. Async Task Pool / Worker Queue
# --------------------------------------------------------------------

class AsyncWorkerPool:
    """
    Worker pool for processing items from a queue.
    
    Example:
        pool = AsyncWorkerPool(worker_count=10)
        await pool.start()
        for item in items:
            await pool.submit(process_item, item)
        results = await pool.join()
    """
    
    def __init__(self, worker_count: int = 5):
        self.worker_count = worker_count
        self._queue = asyncio.Queue()
        self._results = []
        self._workers = []
        self._running = False
    
    async def _worker(self):
        while self._running:
            try:
                func, args, kwargs, future = await self._queue.get()
                try:
                    result = await func(*args, **kwargs)
                    future.set_result(result)
                except Exception as e:
                    future.set_exception(e)
                finally:
                    self._queue.task_done()
            except asyncio.CancelledError:
                break
    
    async def start(self):
        self._running = True
        self._workers = [asyncio.create_task(self._worker()) for _ in range(self.worker_count)]
    
    async def submit(self, func, *args, **kwargs) -> asyncio.Future:
        future = asyncio.Future()
        await self._queue.put((func, args, kwargs, future))
        return future
    
    async def join(self) -> List[Any]:
        await self._queue.join()
        results = []
        for future in self._results:
            results.append(await future)
        return results
    
    async def stop(self):
        self._running = False
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)

# --------------------------------------------------------------------
# 6. Debounce and Throttle
# --------------------------------------------------------------------

class AsyncDebouncer:
    """
    Debounce async function calls: only the last call within window executes.
    
    Example:
        debouncer = AsyncDebouncer(delay=0.3)
        async def search(query):
            return await api.search(query)
        # Only the last call within 0.3s will execute
        result = await debouncer.call(search, query)
    """
    
    def __init__(self, delay: float = 0.1):
        self.delay = delay
        self._task: Optional[asyncio.Task] = None
        self._pending_args = None
        self._pending_kwargs = None
        self._lock = asyncio.Lock()
    
    async def call(self, func, *args, **kwargs):
        async with self._lock:
            self._pending_args = args
            self._pending_kwargs = kwargs
            if self._task is None or self._task.done():
                self._task = asyncio.create_task(self._execute(func))
        return await self._task
    
    async def _execute(self, func):
        await asyncio.sleep(self.delay)
        return await func(*self._pending_args, **self._pending_kwargs)

class AsyncThrottler:
    """
    Throttle async function calls: at most one call per window.
    
    Example:
        throttler = AsyncThrottler(interval=1.0)
        # Subsequent calls within 1s will be delayed
        result = await throttler.call(make_request)
    """
    
    def __init__(self, interval: float = 1.0):
        self.interval = interval
        self._last_call = 0
        self._lock = asyncio.Lock()
    
    async def call(self, func, *args, **kwargs):
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call
            if elapsed < self.interval:
                await asyncio.sleep(self.interval - elapsed)
            self._last_call = time.monotonic()
            return await func(*args, **kwargs)

# --------------------------------------------------------------------
# 7. Background Task Manager
# --------------------------------------------------------------------

class BackgroundTaskManager:
    """
    Manage background async tasks (start, stop, monitor).
    
    Example:
        manager = BackgroundTaskManager()
        await manager.start(background_worker, interval=5)
        await manager.stop()
    """
    
    def __init__(self):
        self._tasks: List[asyncio.Task] = []
        self._stop_event = asyncio.Event()
    
    async def start(self, coro_func: Callable, *args, interval: Optional[float] = None, **kwargs):
        """Start a background task. If interval is provided, runs repeatedly."""
        async def wrapper():
            if interval is None:
                await coro_func(*args, **kwargs)
            else:
                while not self._stop_event.is_set():
                    try:
                        await coro_func(*args, **kwargs)
                    except Exception as e:
                        logger.error(f"Background task error: {e}")
                    await asyncio.sleep(interval)
        task = asyncio.create_task(wrapper())
        self._tasks.append(task)
        return task
    
    async def stop(self, timeout: float = 5.0):
        self._stop_event.set()
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
    
    def is_running(self) -> bool:
        return any(not t.done() for t in self._tasks)

# --------------------------------------------------------------------
# 8. Async Map with Concurrency
# --------------------------------------------------------------------

async def async_map(func: Callable[[T], Awaitable[Any]], 
                    items: List[T], 
                    concurrency: int = 10,
                    ordered: bool = True) -> List[Any]:
    """
    Map an async function over a list with concurrency limit.
    
    Args:
        func: Async function to apply
        items: List of inputs
        concurrency: Max concurrent executions
        ordered: If True, results are in same order as inputs; else any order
    
    Returns:
        List of results
    """
    semaphore = asyncio.Semaphore(concurrency)
    
    async def worker(idx: int, item: T):
        async with semaphore:
            result = await func(item)
            return idx, result
    
    tasks = [worker(i, item) for i, item in enumerate(items)]
    results = await asyncio.gather(*tasks)
    
    if ordered:
        results_dict = {idx: res for idx, res in results}
        return [results_dict[i] for i in range(len(items))]
    else:
        return [res for _, res in results]

# --------------------------------------------------------------------
# 9. Throttled asyncio.gather
# --------------------------------------------------------------------

async def throttled_gather(*coros, concurrency: int = 10) -> List[Any]:
    """
    Run coroutines with concurrency limit.
    
    Example:
        results = await throttled_gather(*[fetch_url(u) for u in urls], concurrency=5)
    """
    semaphore = asyncio.Semaphore(concurrency)
    
    async def bounded_coro(coro):
        async with semaphore:
            return await coro
    
    return await asyncio.gather(*[bounded_coro(c) for c in coros])

# --------------------------------------------------------------------
# 10. Sleep with jitter (for avoiding thundering herd)
# --------------------------------------------------------------------

async def jitter_sleep(base_seconds: float, jitter_factor: float = 0.2):
    """
    Sleep for base_seconds plus random jitter.
    """
    jitter = base_seconds * jitter_factor * random.random()
    await asyncio.sleep(base_seconds + jitter)

# --------------------------------------------------------------------
# Example usage (commented)
# --------------------------------------------------------------------
"""
# Retry with exponential backoff
@async_retry(max_retries=3)
async def fetch_with_retry():
    return await aiohttp.get('https://api.example.com')

# Timeout
result = await timeout(fetch_with_retry(), timeout_seconds=5, fallback="default")

# Batch processor
processor = BatchProcessor(batch_size=50, concurrency=10)
results = await processor.process(items, process_batch)

# Rate limiter
limiter = RateLimiter(max_calls=10, period=1.0)
async with limiter:
    await make_request()

# Async map
results = await async_map(fetch_url, urls, concurrency=20)

# Background task
manager = BackgroundTaskManager()
await manager.start(health_check_loop, interval=30)
# ... later
await manager.stop()
"""

# ====================================================================================================
# END OF async_utils.py
# ====================================================================================================
