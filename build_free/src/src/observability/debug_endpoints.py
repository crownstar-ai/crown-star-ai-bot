# observability/debug_endpoints.py – Performance profiling endpoints
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import FileResponse, HTMLResponse
import os
import glob
import time
from typing import List
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/debug", tags=["Debug"])

@router.get("/pprof/profile")
async def pprof_profile(seconds: int = 30, user: dict = Depends(require_permission("admin"))):
    """Run CPU profiling for N seconds and return profile data"""
    import cProfile
    import io
    import pstats
    profiler = cProfile.Profile()
    profiler.enable()
    time.sleep(seconds)
    profiler.disable()
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats("cumulative")
    ps.print_stats(50)
    return {"profile": s.getvalue()[:100000], "note": "Profile output truncated to 100k chars"}

@router.get("/pprof/flamegraph")
async def flamegraph(seconds: int = 30, user: dict = Depends(require_permission("admin"))):
    """Generate flamegraph SVG (requires py-spy)"""
    from .profiling import generate_cpu_flamegraph
    output = f"data/profiles/flamegraph_{int(time.time())}.svg"
    try:
        result = generate_cpu_flamegraph(duration=seconds, output=output)
        if result and os.path.exists(result):
            return FileResponse(result, media_type="image/svg+xml", filename="flamegraph.svg")
        else:
            return {"error": "Flamegraph generation failed. Install py-spy: pip install py-spy"}
    except Exception as e:
        raise HTTPException(500, str(e))

@router.get("/pprof/heap")
async def heap_profile(user: dict = Depends(require_permission("admin"))):
    """Return heap memory usage (tracemalloc)"""
    import tracemalloc
    tracemalloc.start()
    snapshot = tracemalloc.take_snapshot()
    top_stats = snapshot.statistics('lineno')[:20]
    result = []
    for stat in top_stats:
        result.append(f"{stat.traceback.format()[-1]}: {stat.size/1024:.1f} KiB")
    tracemalloc.stop()
    return {"heap_profile": result}

@router.get("/pprof/block")
async def block_profile(seconds: int = 10, user: dict = Depends(require_permission("admin"))):
    """Block profiling (requires enabling with tracemalloc)"""
    # Placeholder – would use block profiler
    return {"message": "Block profiling not implemented in this version"}

@router.get("/traces")
async def list_traces(user: dict = Depends(require_permission("admin"))):
    """List recent traces from Jaeger (simulated)"""
    # In production, query Jaeger API
    return {"traces": "Query Jaeger UI at http://localhost:16686 for detailed traces"}
