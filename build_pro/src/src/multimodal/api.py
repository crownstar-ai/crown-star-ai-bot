# multimodal/api.py – REST API for multi‑modal embedding and retrieval
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import List, Dict, Optional
from .core import get_mm_manager
from security.dependencies import require_permission
import base64
import io
from PIL import Image

router = APIRouter(prefix="/v1/multimodal", tags=["Multi‑Modal"])

class TextEmbedRequest(BaseModel):
    text: str

class IndexTextRequest(BaseModel):
    text_id: str
    text: str
    metadata: Optional[Dict] = None

class SearchTextRequest(BaseModel):
    query: str
    top_k: int = 10

@router.post("/embed/text")
async def embed_text(req: TextEmbedRequest, user=Depends(require_permission("admin"))):
    """Generate embedding for a text string."""
    mgr = get_mm_manager()
    embedding = mgr.embed_text(req.text)
    return {"embedding": embedding, "dimension": len(embedding)}

@router.post("/embed/image")
async def embed_image(file: UploadFile = File(...), user=Depends(require_permission("admin"))):
    """Generate embedding for an uploaded image."""
    contents = await file.read()
    img = Image.open(io.BytesIO(contents))
    # Save temporarily or process in memory
    mgr = get_mm_manager()
    # For simplicity, we need a file path; we can save to temp
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        img.save(tmp.name)
        embedding = mgr.embed_image(tmp.name)
    os.unlink(tmp.name)
    return {"embedding": embedding, "dimension": len(embedding)}

@router.post("/index/text")
async def index_text(req: IndexTextRequest, user=Depends(require_permission("admin"))):
    """Index a text document for retrieval."""
    mgr = get_mm_manager()
    success = mgr.index_text(req.text_id, req.text, req.metadata)
    if not success:
        raise HTTPException(500, "Indexing failed")
    return {"status": "indexed", "id": req.text_id}

@router.post("/index/image")
async def index_image(file: UploadFile = File(...), image_id: str = Form(...), metadata: Optional[str] = Form(None), user=Depends(require_permission("admin"))):
    """Index an image for retrieval."""
    contents = await file.read()
    img = Image.open(io.BytesIO(contents))
    import tempfile, os, json
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        img.save(tmp.name)
        mgr = get_mm_manager()
        meta = json.loads(metadata) if metadata else {}
        success = mgr.index_image(image_id, tmp.name, meta)
    os.unlink(tmp.name)
    if not success:
        raise HTTPException(500, "Image indexing failed")
    return {"status": "indexed", "id": image_id}

@router.post("/search/text")
async def search_by_text(req: SearchTextRequest, user=Depends(require_permission("admin"))):
    """Search indexed documents using text query."""
    mgr = get_mm_manager()
    results = mgr.search_text(req.query, req.top_k)
    return {"results": results}

@router.post("/search/image")
async def search_by_image(file: UploadFile = File(...), top_k: int = 10, user=Depends(require_permission("admin"))):
    """Search indexed documents using an image query."""
    contents = await file.read()
    img = Image.open(io.BytesIO(contents))
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        img.save(tmp.name)
        mgr = get_mm_manager()
        results = mgr.search_image(tmp.name, top_k)
    os.unlink(tmp.name)
    return {"results": results}

@router.post("/search/hybrid")
async def hybrid_search_text(req: SearchTextRequest, user=Depends(require_permission("admin"))):
    """Hybrid search using dense + sparse retrieval."""
    mgr = get_mm_manager()
    results = mgr.hybrid_search_text(req.query, req.top_k)
    return {"results": results}
