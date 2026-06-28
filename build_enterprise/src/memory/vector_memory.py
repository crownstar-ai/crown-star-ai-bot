# vector_memory.py – FAISS‑based semantic memory with unlimited history
import os, json, sqlite3, numpy as np, faiss, pickle
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any, Optional
from datetime import datetime

class CrownStarVectorMemory:
    def __init__(self, db_path: str = "data/conversations/crownstar_memory.db",
                       embed_model: str = "all-MiniLM-L6-v2"):
        self.db_path = db_path
        self.embedder = SentenceTransformer(embed_model)
        self.dim = 384
        self.index = None
        self.id_to_text = {}
        self._init_db()
        self._init_index()

    def _init_db(self):
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS memory_vectors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER,
                embedding_blob BLOB,
                text_preview TEXT,
                timestamp TEXT,
                metadata TEXT
            )
        ''')
        self.conn.commit()

    def _init_index(self):
        index_path = "data/memory_store/faiss.index"
        map_path = "data/memory_store/id_map.pkl"
        os.makedirs("data/memory_store", exist_ok=True)
        if os.path.exists(index_path):
            self.index = faiss.read_index(index_path)
            if os.path.exists(map_path):
                with open(map_path, 'rb') as f:
                    self.id_to_text = pickle.load(f)
        else:
            self.index = faiss.IndexFlatIP(self.dim)

    def _save_index(self):
        faiss.write_index(self.index, "data/memory_store/faiss.index")
        with open("data/memory_store/id_map.pkl", 'wb') as f:
            pickle.dump(self.id_to_text, f)

    def add_text(self, text: str, conversation_id: int, timestamp: str = None, metadata: dict = None):
        if not text or len(text.strip()) == 0:
            return
        emb = self.embedder.encode([text], normalize_embeddings=True)
        vec_id = self.index.ntotal
        self.index.add(emb.astype(np.float32))
        self.id_to_text[vec_id] = {
            "text": text[:500],
            "conv_id": conversation_id,
            "timestamp": timestamp or datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }
        blob = emb.tobytes()
        meta_json = json.dumps(metadata or {})
        self.conn.execute(
            "INSERT INTO memory_vectors (conversation_id, embedding_blob, text_preview, timestamp, metadata) VALUES (?, ?, ?, ?, ?)",
            (conversation_id, blob, text[:200], timestamp, meta_json)
        )
        self.conn.commit()
        self._save_index()

    def search(self, query: str, k: int = 5) -> List[Dict]:
        if self.index.ntotal == 0:
            return []
        q_emb = self.embedder.encode([query], normalize_embeddings=True).astype(np.float32)
        scores, indices = self.index.search(q_emb, min(k, self.index.ntotal))
        results = []
        for idx, score in zip(indices[0], scores[0]):
            if idx >= 0 and idx in self.id_to_text:
                item = self.id_to_text[idx]
                results.append({
                    "text": item["text"],
                    "conversation_id": item["conv_id"],
                    "timestamp": item["timestamp"],
                    "score": float(score),
                    "metadata": item["metadata"]
                })
        return results

    def close(self):
        self._save_index()
        self.conn.close()
