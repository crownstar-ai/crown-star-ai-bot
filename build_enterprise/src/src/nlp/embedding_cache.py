# nlp/embedding_cache.py – Cache embeddings to avoid recomputation
import sqlite3
import json
import hashlib
from pathlib import Path
from typing import List, Optional
from .service import nlp

class EmbeddingCache:
    def __init__(self, db_path: str = "data/nlp/embedding_cache.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()
    
    def _init_db(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS embeddings (
                text_hash TEXT PRIMARY KEY,
                text_sample TEXT,
                embedding_json TEXT,
                created_at TEXT
            )
        ''')
        self.conn.commit()
    
    def _hash_text(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()
    
    async def get_or_compute(self, text: str) -> List[float]:
        text_hash = self._hash_text(text)
        cursor = self.conn.execute('SELECT embedding_json FROM embeddings WHERE text_hash = ?', (text_hash,))
        row = cursor.fetchone()
        if row:
            return json.loads(row[0])
        # Compute embedding
        embedding = await nlp.get_embedding(text)
        self.conn.execute('INSERT INTO embeddings (text_hash, text_sample, embedding_json, created_at) VALUES (?, ?, ?, ?)',
                         (text_hash, text[:200], json.dumps(embedding), datetime.utcnow().isoformat()))
        self.conn.commit()
        return embedding
    
    def close(self):
        self.conn.close()
