# multimodal/core.py – CrownStar Multi‑Modal Embedding & Retrieval Engine
import os, json, time, hashlib, base64, io
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
import logging
import numpy as np
from PIL import Image
import requests

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------
# Model Provider Abstraction
# --------------------------------------------------------------------
class EmbeddingModelType(Enum):
    CLIP = "clip"
    BLIP = "blip"
    IMAGEBIND = "imagebind"
    ONNX_CLIP = "onnx_clip"

@dataclass
class EmbeddingResult:
    id: str
    modality: str  # "text", "image"
    embedding: List[float]
    model: str
    timestamp: int
    metadata: Dict

class MultiModalEmbedder:
    """Abstract interface for multi‑modal embedding models."""
    def __init__(self, model_name: str = "clip-ViT-B-32", model_type: EmbeddingModelType = EmbeddingModelType.CLIP,
                 device: str = "cpu", cache_dir: str = "data/multimodal/models"):
        self.model_name = model_name
        self.model_type = model_type
        self.device = device
        self.cache_dir = cache_dir
        self._load_model()

    def _load_model(self):
        # Lazy load from HuggingFace or local ONNX
        if self.model_type == EmbeddingModelType.CLIP:
            try:
                from sentence_transformers import SentenceTransformer
                # CLIP model for text and image
                self.model = SentenceTransformer(self.model_name, cache_folder=self.cache_dir)
                self.model.to(self.device)
                self.model.eval()
            except ImportError:
                logger.warning("sentence_transformers not installed, using dummy model")
                self.model = None
        elif self.model_type == EmbeddingModelType.ONNX_CLIP:
            # Use onnxruntime for faster CPU inference
            import onnxruntime as ort
            # Download or load ONNX model
            self.session = ort.InferenceSession(os.path.join(self.cache_dir, "clip_onnx/model.onnx"))
        else:
            self.model = None

    def embed_text(self, texts: List[str], batch_size: int = 32) -> List[np.ndarray]:
        """Generate embeddings for a list of text strings."""
        if self.model is None:
            # Dummy embedding
            return [np.random.randn(512).astype(np.float32) for _ in texts]
        if self.model_type == EmbeddingModelType.CLIP:
            embeddings = self.model.encode(texts, batch_size=batch_size, convert_to_numpy=True)
            return [emb for emb in embeddings]
        return [np.random.randn(512).astype(np.float32) for _ in texts]

    def embed_image(self, images: List[Union[str, Image.Image]], batch_size: int = 16) -> List[np.ndarray]:
        """Generate embeddings for images (file paths, URLs, or PIL Images)."""
        processed = []
        for img in images:
            if isinstance(img, str):
                if img.startswith(('http://', 'https://')):
                    # Download from URL
                    resp = requests.get(img, timeout=30)
                    img = Image.open(io.BytesIO(resp.content))
                else:
                    img = Image.open(img)
            # Convert to RGB if needed
            if img.mode != 'RGB':
                img = img.convert('RGB')
            processed.append(img)
        if self.model is None:
            return [np.random.randn(512).astype(np.float32) for _ in processed]
        if self.model_type == EmbeddingModelType.CLIP:
            # SentenceTransformer CLIP expects images as PIL
            embeddings = self.model.encode(processed, batch_size=batch_size, convert_to_numpy=True)
            return [emb for emb in embeddings]
        return [np.random.randn(512).astype(np.float32) for _ in processed]

# --------------------------------------------------------------------
# Multi‑Modal Search Engine (connects to vector DB)
# --------------------------------------------------------------------
class MultiModalSearch:
    def __init__(self, embedder: MultiModalEmbedder, vector_manager, index_name: str = "multimodal"):
        self.embedder = embedder
        self.vector_manager = vector_manager
        self.index_name = index_name
        # Ensure vector index exists
        self._ensure_index()

    def _ensure_index(self):
        if self.index_name not in self.vector_manager.indexes:
            self.vector_manager.create_index(self.index_name, "faiss", dimension=512, metric="cosine")

    def index_text(self, text_id: str, text: str, metadata: Dict = None) -> bool:
        """Index a text document with its embedding."""
        emb = self.embedder.embed_text([text])[0]
        from vectors.core import VectorDocument
        doc = VectorDocument(
            id=text_id,
            vector=emb.tolist(),
            metadata=metadata or {"modality": "text", "original_text": text[:500]},
            text=text
        )
        self.vector_manager.ingest(self.index_name, [doc])
        return True

    def index_image(self, image_id: str, image_path: str, metadata: Dict = None) -> bool:
        """Index an image with its embedding."""
        emb = self.embedder.embed_image([image_path])[0]
        from vectors.core import VectorDocument
        doc = VectorDocument(
            id=image_id,
            vector=emb.tolist(),
            metadata=metadata or {"modality": "image", "path": image_path},
            text=None
        )
        self.vector_manager.ingest(self.index_name, [doc])
        return True

    def search_by_text(self, query: str, top_k: int = 10) -> List[Dict]:
        """Search for similar documents (text or images) using text query."""
        q_emb = self.embedder.embed_text([query])[0]
        results = self.vector_manager.search(self.index_name, q_emb.tolist(), top_k)
        return results

    def search_by_image(self, image_path: str, top_k: int = 10) -> List[Dict]:
        """Search for similar documents using an image query."""
        q_emb = self.embedder.embed_image([image_path])[0]
        results = self.vector_manager.search(self.index_name, q_emb.tolist(), top_k)
        return results

    def hybrid_search_text(self, query: str, top_k: int = 10) -> List[Dict]:
        """Hybrid search (text + dense) using vector manager's hybrid_search."""
        q_emb = self.embedder.embed_text([query])[0]
        results = self.vector_manager.hybrid_search(self.index_name, query, q_emb.tolist(), top_k)
        return results

# --------------------------------------------------------------------
# Multi‑Modal Manager Singleton
# --------------------------------------------------------------------
class MultiModalManager:
    def __init__(self, config_path="config/multimodal/config.json"):
        self.config = self._load_config(config_path)
        self.embedder = MultiModalEmbedder(
            model_name=self.config.get("model_name", "clip-ViT-B-32"),
            model_type=EmbeddingModelType(self.config.get("model_type", "clip")),
            device=self.config.get("device", "cpu"),
            cache_dir=self.config.get("cache_dir", "data/multimodal/models")
        )
        # Lazy import vector manager to avoid circular
        from vectors.core import get_vector_manager
        self.vector_manager = get_vector_manager()
        self.search_engine = MultiModalSearch(self.embedder, self.vector_manager, self.config.get("index_name", "multimodal"))

    def _load_config(self, path):
        default = {
            "model_name": "clip-ViT-B-32",
            "model_type": "clip",
            "device": "cpu",
            "cache_dir": "data/multimodal/models",
            "index_name": "multimodal",
            "batch_size_text": 32,
            "batch_size_image": 16
        }
        if os.path.exists(path):
            with open(path, 'r') as f:
                user = json.load(f)
                default.update(user)
        return default

    def embed_text(self, text: str) -> List[float]:
        emb = self.embedder.embed_text([text])[0]
        return emb.tolist()

    def embed_image(self, image_path: str) -> List[float]:
        emb = self.embedder.embed_image([image_path])[0]
        return emb.tolist()

    def index_text(self, text_id: str, text: str, metadata: Dict = None) -> bool:
        return self.search_engine.index_text(text_id, text, metadata)

    def index_image(self, image_id: str, image_path: str, metadata: Dict = None) -> bool:
        return self.search_engine.index_image(image_id, image_path, metadata)

    def search_text(self, query: str, top_k: int = 10) -> List[Dict]:
        return self.search_engine.search_by_text(query, top_k)

    def search_image(self, image_path: str, top_k: int = 10) -> List[Dict]:
        return self.search_engine.search_by_image(image_path, top_k)

    def hybrid_search_text(self, query: str, top_k: int = 10) -> List[Dict]:
        return self.search_engine.hybrid_search_text(query, top_k)

_mm_manager = None
def get_mm_manager():
    global _mm_manager
    if _mm_manager is None:
        _mm_manager = MultiModalManager()
    return _mm_manager
