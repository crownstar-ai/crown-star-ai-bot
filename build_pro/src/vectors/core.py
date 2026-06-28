# vectors/core.py – CrownStar Vector Database & Hybrid Search Engine
import os, json, time, hashlib, numpy as np
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging
import pickle

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------
# Vector DB Provider Abstraction
# --------------------------------------------------------------------
class VectorDBProvider(Enum):
    FAISS = "faiss"
    PINECONE = "pinecone"
    QDRANT = "qdrant"
    WEAVIATE = "weaviate"
    SOVEREIGN_AU = "sovereign_au"

@dataclass
class VectorIndexConfig:
    name: str
    provider: VectorDBProvider
    dimension: int = 384
    metric: str = "cosine"  # cosine, dot, l2
    connection_params: Dict = None

@dataclass
class VectorDocument:
    id: str
    vector: List[float]
    metadata: Dict
    text: Optional[str] = None

class VectorDBInterface:
    """Abstract interface for multiple vector databases."""
    def __init__(self, config: VectorIndexConfig):
        self.config = config
        self._init_client()

    def _init_client(self):
        if self.config.provider == VectorDBProvider.FAISS:
            import faiss
            self.client = FAISSClient(self.config)
        elif self.config.provider == VectorDBProvider.PINECONE:
            self.client = PineconeClient(self.config)
        elif self.config.provider == VectorDBProvider.QDRANT:
            self.client = QdrantClient(self.config)
        elif self.config.provider == VectorDBProvider.WEAVIATE:
            self.client = WeaviateClient(self.config)
        elif self.config.provider == VectorDBProvider.SOVEREIGN_AU:
            self.client = SovereignVectorClient(self.config)
        else:
            raise ValueError(f"Unknown provider {self.config.provider}")

    def upsert(self, documents: List[VectorDocument]) -> bool:
        return self.client.upsert(documents)

    def search(self, query_vector: List[float], top_k: int = 10, filter: Dict = None) -> List[Tuple[str, float, Dict]]:
        return self.client.search(query_vector, top_k, filter)

    def delete(self, ids: List[str]) -> bool:
        return self.client.delete(ids)

    def get_index_stats(self) -> Dict:
        return self.client.get_stats()

# --------------------------------------------------------------------
# Provider Implementations (simplified stubs)
# --------------------------------------------------------------------
class FAISSClient:
    def __init__(self, config):
        import faiss
        self.dimension = config.dimension
        self.metric = config.metric
        self.index = None
        self.id_to_index = {}
        self.metadata = []
        self._load_or_create()

    def _load_or_create(self):
        index_path = f"data/vectors/indexes/{self.config.name}.faiss"
        meta_path = f"data/vectors/indexes/{self.config.name}.meta"
        if os.path.exists(index_path):
            self.index = faiss.read_index(index_path)
            with open(meta_path, 'rb') as f:
                self.metadata, self.id_to_index = pickle.load(f)
        else:
            if self.metric == "cosine":
                self.index = faiss.IndexFlatIP(self.dimension)  # inner product, need normalized vectors
            else:
                self.index = faiss.IndexFlatL2(self.dimension)

    def upsert(self, documents):
        for doc in documents:
            vec = np.array(doc.vector, dtype=np.float32)
            if self.metric == "cosine":
                vec = vec / (np.linalg.norm(vec) + 1e-8)
            self.index.add(vec.reshape(1, -1))
            idx = self.index.ntotal - 1
            self.id_to_index[doc.id] = idx
            self.metadata.append({"id": doc.id, "metadata": doc.metadata, "text": doc.text})
        self._save()
        return True

    def _save(self):
        faiss.write_index(self.index, f"data/vectors/indexes/{self.config.name}.faiss")
        with open(f"data/vectors/indexes/{self.config.name}.meta", 'wb') as f:
            pickle.dump((self.metadata, self.id_to_index), f)

    def search(self, query_vector, top_k, filter=None):
        q = np.array(query_vector, dtype=np.float32)
        if self.metric == "cosine":
            q = q / (np.linalg.norm(q) + 1e-8)
        distances, indices = self.index.search(q.reshape(1, -1), top_k)
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx >= 0 and idx < len(self.metadata):
                meta = self.metadata[idx]
                results.append((meta["id"], float(dist), meta["metadata"]))
        return results

    def delete(self, ids):
        # Simplified: rebuild index without those IDs
        return True

    def get_stats(self):
        return {"total_vectors": self.index.ntotal, "dimension": self.dimension}

class PineconeClient:
    def __init__(self, config):
        # would initialize Pinecone
        pass
    def upsert(self, docs): return True
    def search(self, qv, k, f): return []
    def delete(self, ids): return True
    def get_stats(self): return {"total_vectors": 0}

class QdrantClient:
    def __init__(self, config): pass
    def upsert(self, docs): return True
    def search(self, qv, k, f): return []
    def delete(self, ids): return True
    def get_stats(self): return {"total_vectors": 0}

class WeaviateClient:
    def __init__(self, config): pass
    def upsert(self, docs): return True
    def search(self, qv, k, f): return []
    def delete(self, ids): return True
    def get_stats(self): return {"total_vectors": 0}

class SovereignVectorClient:
    def __init__(self, config): pass
    def upsert(self, docs): return True
    def search(self, qv, k, f): return []
    def delete(self, ids): return True
    def get_stats(self): return {"total_vectors": 0}

# --------------------------------------------------------------------
# Hybrid Search (Dense + Sparse)
# --------------------------------------------------------------------
class BM25Index:
    """Simple BM25 for sparse retrieval (keyword search)."""
    def __init__(self):
        self.documents = []
        self.tokenized = []
        self.idf = {}
        self.avg_doc_len = 0

    def tokenize(self, text):
        return text.lower().split()

    def build(self, documents: List[Tuple[str, str]]):  # (doc_id, text)
        self.documents = documents
        self.tokenized = [self.tokenize(text) for _, text in documents]
        doc_count = len(documents)
        term_doc_freq = {}
        for tokens in self.tokenized:
            unique = set(tokens)
            for term in unique:
                term_doc_freq[term] = term_doc_freq.get(term, 0) + 1
        for term, df in term_doc_freq.items():
            self.idf[term] = np.log((doc_count - df + 0.5) / (df + 0.5) + 1)
        self.avg_doc_len = sum(len(t) for t in self.tokenized) / doc_count

    def search(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
        query_tokens = self.tokenize(query)
        scores = []
        for idx, tokens in enumerate(self.tokenized):
            score = 0.0
            for token in set(query_tokens):
                if token not in self.idf:
                    continue
                tf = tokens.count(token)
                k1 = 1.5
                b = 0.75
                doc_len = len(tokens)
                bm25_score = self.idf[token] * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_len / self.avg_doc_len))
                score += bm25_score
            scores.append((self.documents[idx][0], score))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

class HybridSearchEngine:
    """
    Combines dense vector search (FAISS) with sparse keyword search (BM25)
    using Reciprocal Rank Fusion (RRF) or weighted sum.
    """
    def __init__(self, dense_index: VectorDBInterface, bm25_index: BM25Index, weight_dense: float = 0.6, weight_sparse: float = 0.4):
        self.dense_index = dense_index
        self.bm25_index = bm25_index
        self.weight_dense = weight_dense
        self.weight_sparse = weight_sparse

    def search(self, query: str, query_vector: List[float], top_k: int = 10) -> List[Dict]:
        # Dense search
        dense_results = self.dense_index.search(query_vector, top_k * 2)
        # Sparse search
        sparse_results = self.bm25_index.search(query, top_k * 2)
        # Reciprocal Rank Fusion
        scores = {}
        for rank, (doc_id, _, _) in enumerate(dense_results):
            scores[doc_id] = scores.get(doc_id, 0) + self.weight_dense / (rank + 60)
        for rank, (doc_id, bm25_score) in enumerate(sparse_results):
            scores[doc_id] = scores.get(doc_id, 0) + self.weight_sparse / (rank + 60)
        # Sort and return
        sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [{"id": doc_id, "fusion_score": score} for doc_id, score in sorted_docs]

# --------------------------------------------------------------------
# Re‑ranking (Cross‑Encoder)
# --------------------------------------------------------------------
class CrossEncoderReranker:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model = None
        # Would load cross‑encoder model
    def rerank(self, query: str, documents: List[Dict]) -> List[Dict]:
        # Simplified: return original order with dummy scores
        for i, doc in enumerate(documents):
            doc["rerank_score"] = 1.0 / (i + 1)
        return sorted(documents, key=lambda x: x.get("rerank_score", 0), reverse=True)

# --------------------------------------------------------------------
# Vector Manager Singleton
# --------------------------------------------------------------------
class VectorManager:
    def __init__(self, config_path="config/vectors/vector_config.json"):
        self.config = self._load_config(config_path)
        self.indexes: Dict[str, VectorDBInterface] = {}
        self.bm25_indexes: Dict[str, BM25Index] = {}
        self.hybrid_engines: Dict[str, HybridSearchEngine] = {}
        self.reranker = CrossEncoderReranker()
        self._load_indexes()

    def _load_config(self, path):
        default = {
            "default_index": "crownstar_main",
            "indexes": [
                {
                    "name": "crownstar_main",
                    "provider": "faiss",
                    "dimension": 384,
                    "metric": "cosine"
                }
            ]
        }
        if os.path.exists(path):
            with open(path, 'r') as f:
                user = json.load(f)
                default.update(user)
        return default

    def _load_indexes(self):
        for idx_cfg in self.config["indexes"]:
            provider = VectorDBProvider(idx_cfg["provider"])
            config = VectorIndexConfig(
                name=idx_cfg["name"],
                provider=provider,
                dimension=idx_cfg.get("dimension", 384),
                metric=idx_cfg.get("metric", "cosine"),
                connection_params=idx_cfg.get("connection_params", {})
            )
            self.indexes[idx_cfg["name"]] = VectorDBInterface(config)
            # Also create BM25 index for hybrid search
            self.bm25_indexes[idx_cfg["name"]] = BM25Index()
            self.hybrid_engines[idx_cfg["name"]] = HybridSearchEngine(
                self.indexes[idx_cfg["name"]], self.bm25_indexes[idx_cfg["name"]]
            )

    def create_index(self, name: str, provider: str, dimension: int = 384, metric: str = "cosine") -> bool:
        if name in self.indexes:
            return False
        cfg = VectorIndexConfig(name=name, provider=VectorDBProvider(provider), dimension=dimension, metric=metric)
        self.indexes[name] = VectorDBInterface(cfg)
        self.bm25_indexes[name] = BM25Index()
        self.hybrid_engines[name] = HybridSearchEngine(self.indexes[name], self.bm25_indexes[name])
        # Save config
        self.config["indexes"].append({"name": name, "provider": provider, "dimension": dimension, "metric": metric})
        self._save_config()
        return True

    def _save_config(self):
        with open("config/vectors/vector_config.json", 'w') as f:
            json.dump(self.config, f, indent=2)

    def ingest(self, index_name: str, documents: List[VectorDocument]) -> int:
        idx = self.indexes.get(index_name)
        if not idx:
            raise ValueError(f"Index {index_name} not found")
        # Also add to BM25 index for hybrid search
        bm25 = self.bm25_indexes.get(index_name)
        if bm25:
            for doc in documents:
                if doc.text:
                    bm25.build([(doc.id, doc.text)])  # incremental rebuild needed
        idx.upsert(documents)
        return len(documents)

    def search(self, index_name: str, query_vector: List[float], top_k: int = 10) -> List[Dict]:
        idx = self.indexes.get(index_name)
        if not idx:
            raise ValueError(f"Index {index_name} not found")
        results = idx.search(query_vector, top_k)
        return [{"id": r[0], "score": r[1], "metadata": r[2]} for r in results]

    def hybrid_search(self, index_name: str, query: str, query_vector: List[float], top_k: int = 10) -> List[Dict]:
        hybrid = self.hybrid_engines.get(index_name)
        if not hybrid:
            raise ValueError(f"Index {index_name} not found")
        results = hybrid.search(query, query_vector, top_k)
        return results

    def rerank(self, query: str, documents: List[Dict]) -> List[Dict]:
        return self.reranker.rerank(query, documents)

    def get_stats(self, index_name: str) -> Dict:
        idx = self.indexes.get(index_name)
        if not idx:
            return {}
        return idx.get_index_stats()

_vector_manager = None
def get_vector_manager():
    global _vector_manager
    if _vector_manager is None:
        _vector_manager = VectorManager()
    return _vector_manager
