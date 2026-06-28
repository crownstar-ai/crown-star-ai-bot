# vectors/api.py – REST API for vector database management
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
from .core import get_vector_manager, VectorDocument
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/vectors", tags=["Vector DB"])

class IndexCreateRequest(BaseModel):
    name: str
    provider: str = "faiss"
    dimension: int = 384
    metric: str = "cosine"

class VectorIngestRequest(BaseModel):
    documents: List[Dict]  # each: {"id": str, "vector": List[float], "metadata": Dict, "text": Optional[str]}

class SearchRequest(BaseModel):
    query_vector: List[float]
    top_k: int = 10
    index_name: str

class HybridSearchRequest(BaseModel):
    query: str
    query_vector: List[float]
    top_k: int = 10
    index_name: str

class RerankRequest(BaseModel):
    query: str
    documents: List[Dict]

@router.post("/indexes/create")
async def create_index(req: IndexCreateRequest, user=Depends(require_permission("admin"))):
    """Create a new vector index."""
    mgr = get_vector_manager()
    success = mgr.create_index(req.name, req.provider, req.dimension, req.metric)
    if not success:
        raise HTTPException(400, "Index already exists")
    return {"status": "created", "name": req.name}

@router.get("/indexes")
async def list_indexes(user=Depends(require_permission("admin"))):
    """List all vector indexes."""
    mgr = get_vector_manager()
    return {"indexes": list(mgr.indexes.keys())}

@router.post("/ingest")
async def ingest_vectors(req: VectorIngestRequest, user=Depends(require_permission("admin"))):
    """Ingest vectors into a named index (must specify index_name in each doc metadata)."""
    mgr = get_vector_manager()
    # Assume all docs go to same index; pick from first doc
    if not req.documents:
        raise HTTPException(400, "No documents")
    index_name = req.documents[0].get("index_name", "crownstar_main")
    docs = [VectorDocument(
        id=d["id"],
        vector=d["vector"],
        metadata=d.get("metadata", {}),
        text=d.get("text")
    ) for d in req.documents]
    count = mgr.ingest(index_name, docs)
    return {"ingested": count, "index": index_name}

@router.post("/search")
async def vector_search(req: SearchRequest, user=Depends(require_permission("admin"))):
    """Perform dense vector search."""
    mgr = get_vector_manager()
    results = mgr.search(req.index_name, req.query_vector, req.top_k)
    return {"results": results}

@router.post("/hybrid_search")
async def hybrid_search(req: HybridSearchRequest, user=Depends(require_permission("admin"))):
    """Perform hybrid search (dense + sparse with RRF)."""
    mgr = get_vector_manager()
    results = mgr.hybrid_search(req.index_name, req.query, req.query_vector, req.top_k)
    return {"results": results}

@router.post("/rerank")
async def rerank_documents(req: RerankRequest, user=Depends(require_permission("admin"))):
    """Re‑rank search results using a cross‑encoder."""
    mgr = get_vector_manager()
    reranked = mgr.rerank(req.query, req.documents)
    return {"reranked": reranked}

@router.get("/stats/{index_name}")
async def index_stats(index_name: str, user=Depends(require_permission("admin"))):
    """Get statistics for a vector index."""
    mgr = get_vector_manager()
    stats = mgr.get_stats(index_name)
    return stats
