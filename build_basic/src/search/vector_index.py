# src/search/vector_index.py – Full VectorIndex with FAISS, saving, loading, search
import numpy as np
import faiss
import pickle
import hashlib
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

class VectorIndex:
    def __init__(self, dimension: int = 384, index_type: str = "FlatIP"):
        self.dimension = dimension
        self.index_type = index_type
        self.index = faiss.IndexFlatIP(dimension) if index_type == "FlatIP" else faiss.IndexFlatL2(dimension)
        self.metadata = []  # list of dicts aligned with index
        self.doc_id_to_index = {}
        self._encoder = None  # sentence‑transformer would be loaded lazily
        self.persistence_dir = Path("data/vectors")
        self.persistence_dir.mkdir(parents=True, exist_ok=True)

    def _get_encoder(self):
        if self._encoder is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._encoder = SentenceTransformer('all-MiniLM-L6-v2')
            except ImportError:
                raise RuntimeError("sentence_transformers not installed")
        return self._encoder

    def _normalize(self, vectors: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        return vectors / norms

    def add_document(self, text: str, metadata: Optional[Dict] = None) -> bool:
        encoder = self._get_encoder()
        embedding = encoder.encode([text], normalize_embeddings=True)[0].astype(np.float32).reshape(1, -1)
        doc_id = hashlib.md5(text.encode()).hexdigest()
        if doc_id in self.doc_id_to_index:
            return False
        self.index.add(embedding)
        idx = self.index.ntotal - 1
        meta = metadata or {}
        meta["_id"] = doc_id
        meta["_text_preview"] = text[:200]
        meta["_timestamp"] = time.time()
        self.metadata.append(meta)
        self.doc_id_to_index[doc_id] = idx
        return True

    def search(self, query: str, k: int = 5) -> List[Dict]:
        if self.index.ntotal == 0:
            return []
        encoder = self._get_encoder()
        q_emb = encoder.encode([query], normalize_embeddings=True)[0].astype(np.float32).reshape(1, -1)
        scores, indices = self.index.search(q_emb, min(k, self.index.ntotal))
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1 or idx >= len(self.metadata):
                continue
            res = dict(self.metadata[idx])
            res["_score"] = float(score)
            results.append(res)
        return results

    def load(self, name: str = "crownstar_index"):
        index_path = self.persistence_dir / f"{name}.faiss"
        meta_path = self.persistence_dir / f"{name}.meta"
        ids_path = self.persistence_dir / f"{name}.ids"
        if index_path.exists():
            self.index = faiss.read_index(str(index_path))
            with open(meta_path, 'rb') as f:
                self.metadata = pickle.load(f)
            with open(ids_path, 'rb') as f:
                self.doc_id_to_index = pickle.load(f)
        else:
            # Fresh start
            pass

    def save(self, name: str = "crownstar_index"):
        index_path = self.persistence_dir / f"{name}.faiss"
        meta_path = self.persistence_dir / f"{name}.meta"
        ids_path = self.persistence_dir / f"{name}.ids"
        faiss.write_index(self.index, str(index_path))
        with open(meta_path, 'wb') as f:
            pickle.dump(self.metadata, f)
        with open(ids_path, 'wb') as f:
            pickle.dump(self.doc_id_to_index, f)
