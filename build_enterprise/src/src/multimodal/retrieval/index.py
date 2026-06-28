# multimodal/retrieval/index.py – FAISS index for cross‑modal search
import numpy as np
import faiss
import pickle
import os
from typing import List, Tuple, Dict
from datetime import datetime
import hashlib

class MultiModalIndex:
    def __init__(self, index_path: str = "data/multimodal/index.faiss", metadata_path: str = "data/multimodal/metadata.pkl"):
        self.index_path = index_path
        self.metadata_path = metadata_path
        self.dim = 512  # CLIP embedding dimension
        self.index = None
        self.metadata = []  # list of dicts: {id, type, text, path, timestamp}
        self._load_or_create()
    
    def _load_or_create(self):
        if os.path.exists(self.index_path):
            self.index = faiss.read_index(self.index_path)
            if os.path.exists(self.metadata_path):
                with open(self.metadata_path, "rb") as f:
                    self.metadata = pickle.load(f)
        else:
            self.index = faiss.IndexFlatIP(self.dim)  # inner product (cosine after normalize)
            self.metadata = []
    
    def _save(self):
        faiss.write_index(self.index, self.index_path)
        with open(self.metadata_path, "wb") as f:
            pickle.dump(self.metadata, f)
    
    def add(self, embedding: np.ndarray, item_type: str, text: str, path: str = None):
        """Add embedding to index with metadata"""
        # Normalize
        embedding = embedding / (np.linalg.norm(embedding) + 1e-10)
        self.index.add(embedding.reshape(1, -1).astype(np.float32))
        self.metadata.append({
            "id": hashlib.md5(f"{embedding.tobytes()}{datetime.utcnow().isoformat()}".encode()).hexdigest()[:8],
            "type": item_type,
            "text": text,
            "path": path,
            "timestamp": datetime.utcnow().isoformat()
        })
        self._save()
    
    def search(self, query_embedding: np.ndarray, k: int = 5) -> List[Tuple[Dict, float]]:
        """Search nearest neighbours by embedding"""
        query = query_embedding / (np.linalg.norm(query_embedding) + 1e-10)
        scores, indices = self.index.search(query.reshape(1, -1).astype(np.float32), k)
        results = []
        for idx, score in zip(indices[0], scores[0]):
            if idx >= 0 and idx < len(self.metadata):
                results.append((self.metadata[idx], float(score)))
        return results
    
    def search_by_text(self, text: str, k: int = 5) -> List[Tuple[Dict, float]]:
        """Search using text embedding (CLIP text)"""
        from ..service import get_mm_service
        mm = get_mm_service()
        emb = mm.get_text_embedding(text)
        return self.search(emb, k)
    
    def search_by_image(self, image_data, k: int = 5) -> List[Tuple[Dict, float]]:
        from ..service import get_mm_service
        mm = get_mm_service()
        emb = mm.get_image_embedding(image_data)
        return self.search(emb, k)

_mm_index = None
def get_mm_index():
    global _mm_index
    if _mm_index is None:
        _mm_index = MultiModalIndex()
    return _mm_index
