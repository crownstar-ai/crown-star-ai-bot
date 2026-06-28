# canvas/api.py – REST API for canvas operations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import uuid
import time
from dataclasses import asdict
from .core import get_canvas_manager, CanvasStroke, CanvasRenderer
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/canvas", tags=["Canvas"])

class CreateCanvasRequest(BaseModel):
    width: int = 800
    height: int = 600
    background: str = "#ffffff"

class StrokeRequest(BaseModel):
    canvas_id: str
    points: List[List[int]]
    color: str
    width: int

class GenerateRequest(BaseModel):
    prompt: str
    width: int = 800
    height: int = 600

@router.post("/create")
async def create_canvas(req: CreateCanvasRequest, user=Depends(require_permission("admin"))):
    mgr = get_canvas_manager()
    state = mgr.create_canvas(req.width, req.height, req.background, created_by=user.get("user_id", "unknown"))
    return {"canvas_id": state.canvas_id, "width": state.width, "height": state.height}

@router.post("/stroke")
async def add_stroke(req: StrokeRequest, user=Depends(require_permission("admin"))):
    mgr = get_canvas_manager()
    stroke = CanvasStroke(
        id=str(uuid.uuid4()),
        points=[(p[0], p[1]) for p in req.points],
        color=req.color,
        width=req.width,
        timestamp=int(time.time())
    )
    state = mgr.add_stroke(req.canvas_id, stroke)
    return {"version": state.version}

@router.post("/undo/{canvas_id}")
async def undo(canvas_id: str, user=Depends(require_permission("admin"))):
    mgr = get_canvas_manager()
    state = mgr.undo(canvas_id)
    return {"version": state.version if state else 0}

@router.post("/generate")
async def generate_from_text(req: GenerateRequest, user=Depends(require_permission("admin"))):
    mgr = get_canvas_manager()
    state = mgr.generate_from_text(req.prompt, req.width, req.height)
    return {"canvas_id": state.canvas_id, "preview_base64": CanvasRenderer.render_to_base64(state)}

@router.get("/{canvas_id}")
async def get_canvas(canvas_id: str, format: str = "json", user=Depends(require_permission("admin"))):
    mgr = get_canvas_manager()
    state = mgr.get_canvas(canvas_id)
    if not state:
        raise HTTPException(404, "Canvas not found")
    if format == "png":
        from fastapi.responses import Response
        import io
        img = CanvasRenderer.render_to_pil(state)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return Response(content=buf.getvalue(), media_type="image/png")
    elif format == "svg":
        from fastapi.responses import Response
        svg = CanvasRenderer.render_to_svg(state)
        return Response(content=svg, media_type="image/svg+xml")
    else:
        return asdict(state)

@router.get("/embedding/{canvas_id}")
async def get_canvas_embedding(canvas_id: str, user=Depends(require_permission("admin"))):
    mgr = get_canvas_manager()
    emb = mgr.get_snapshot_embedding(canvas_id)
    if emb is None:
        raise HTTPException(404, "Embedding not available")
    return {"embedding": emb, "dimension": len(emb)}
