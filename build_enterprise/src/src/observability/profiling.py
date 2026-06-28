# observability/profiling.py – CPU and memory profiling middleware
import cProfile
import pstats
import io
import time
import os
import threading
from functools import wraps
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional

class ProfilingMiddleware(BaseHTTPMiddleware):
    """Profile requests that take longer than threshold"""
    def __init__(self, app, threshold_ms: int = 1000, profile_dir: str = "data/profiles"):
        super().__init__(app)
        self.threshold_ms = threshold_ms
        self.profile_dir = profile_dir
        os.makedirs(profile_dir, exist_ok=True)
    
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        
        # Start profiler if slow path expected
        profiler = None
        if request.headers.get("X-Profile") == "true":
            profiler = cProfile.Profile()
            profiler.enable()
        
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        
        if duration_ms > self.threshold_ms or profiler:
            if profiler:
                profiler.disable()
                s = io.StringIO()
                ps = pstats.Stats(profiler, stream=s).sort_stats("cumulative")
                ps.print_stats(20)
                profile_path = os.path.join(self.profile_dir, f"profile_{int(time.time())}_{request.url.path.replace('/','_')}.txt")
                with open(profile_path, 'w') as f:
                    f.write(s.getvalue())
                response.headers["X-Profile-Saved"] = profile_path
            else:
                # Log slow request
                print(f"Slow request: {request.method} {request.url.path} took {duration_ms:.2f}ms")
        
        response.headers["X-Duration-Ms"] = str(int(duration_ms))
        return response

def start_py_spy(pid: Optional[int] = None, output_file: str = "data/profiles/flamegraph.svg"):
    """Start py-spy profiler in background (requires py-spy installed)"""
    import subprocess
    pid = pid or os.getpid()
    cmd = ["py-spy", "record", "-o", output_file, "-p", str(pid), "--duration", "60", "--format", "svg"]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"py-spy recording started for PID {pid} -> {output_file}")
        return proc
    except FileNotFoundError:
        print("py-spy not found. Install with: pip install py-spy")
        return None

def generate_cpu_flamegraph(duration: int = 30, output: str = "data/profiles/flamegraph.svg") -> str:
    """Generate CPU flamegraph using py-spy (non‑blocking)"""
    proc = start_py_spy(output_file=output)
    if proc:
        import time
        time.sleep(duration)
        proc.terminate()
        return output
    return ""
