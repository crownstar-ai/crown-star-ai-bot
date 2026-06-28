# multimodal/service.py – Core multi‑modal processing (CLIP, Whisper, BLIP)
import os
import base64
import io
import time
from typing import Dict, List, Tuple, Optional, Union
import numpy as np
from PIL import Image
import tempfile

# Lazy loading of heavy models
_clip_model = None
_clip_processor = None
_whisper_model = None
_blip_processor = None
_blip_model = None

def _load_clip():
    global _clip_model, _clip_processor
    if _clip_model is None:
        try:
            from transformers import CLIPModel, CLIPProcessor
            _clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
            _clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
            print("CLIP model loaded")
        except ImportError:
            print("transformers not installed. Install with: pip install transformers torch pillow")
    return _clip_model, _clip_processor

def _load_whisper():
    global _whisper_model
    if _whisper_model is None:
        try:
            import whisper
            _whisper_model = whisper.load_model("base")
            print("Whisper model loaded")
        except ImportError:
            print("whisper not installed. Install with: pip install openai-whisper")
    return _whisper_model

def _load_blip():
    global _blip_model, _blip_processor
    if _blip_model is None:
        try:
            from transformers import BlipProcessor, BlipForConditionalGeneration
            _blip_processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
            _blip_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
            print("BLIP image captioning model loaded")
        except ImportError:
            print("transformers not installed – image captioning disabled")
    return _blip_model, _blip_processor

class MultiModalService:
    @staticmethod
    def get_image_embedding(image_data: Union[str, bytes, Image.Image]) -> np.ndarray:
        """Get CLIP embedding for image (512‑dim)"""
        model, processor = _load_clip()
        if model is None:
            return np.zeros(512)
        if isinstance(image_data, str) and image_data.startswith("data:image"):
            # base64 image
            img_bytes = base64.b64decode(image_data.split(",")[1])
            image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        elif isinstance(image_data, bytes):
            image = Image.open(io.BytesIO(image_data)).convert("RGB")
        elif isinstance(image_data, Image.Image):
            image = image_data
        else:
            raise ValueError("Unsupported image input")
        inputs = processor(images=image, return_tensors="pt")
        with torch.no_grad():
            embeddings = model.get_image_features(**inputs)
        return embeddings.cpu().numpy().flatten()
    
    @staticmethod
    def get_text_embedding(text: str) -> np.ndarray:
        """Get CLIP text embedding (512‑dim)"""
        model, processor = _load_clip()
        if model is None:
            return np.zeros(512)
        inputs = processor(text=text, return_tensors="pt", padding=True)
        with torch.no_grad():
            embeddings = model.get_text_features(**inputs)
        return embeddings.cpu().numpy().flatten()
    
    @staticmethod
    def zero_shot_classify(image_data: Union[str, bytes, Image.Image], candidate_labels: List[str]) -> List[Tuple[str, float]]:
        """Zero‑shot image classification using CLIP"""
        model, processor = _load_clip()
        if model is None:
            return [(label, 0.0) for label in candidate_labels]
        if isinstance(image_data, str) and image_data.startswith("data:image"):
            img_bytes = base64.b64decode(image_data.split(",")[1])
            image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        elif isinstance(image_data, bytes):
            image = Image.open(io.BytesIO(image_data)).convert("RGB")
        else:
            image = image_data
        inputs = processor(text=candidate_labels, images=image, return_tensors="pt", padding=True)
        with torch.no_grad():
            outputs = model(**inputs)
            logits_per_image = outputs.logits_per_image
            probs = logits_per_image.softmax(dim=1).cpu().numpy()[0]
        return [(label, float(prob)) for label, prob in zip(candidate_labels, probs)]
    
    @staticmethod
    def caption_image(image_data: Union[str, bytes, Image.Image]) -> str:
        """Generate image caption using BLIP"""
        model, processor = _load_blip()
        if model is None:
            return "Image captioning unavailable"
        if isinstance(image_data, str) and image_data.startswith("data:image"):
            img_bytes = base64.b64decode(image_data.split(",")[1])
            image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        elif isinstance(image_data, bytes):
            image = Image.open(io.BytesIO(image_data)).convert("RGB")
        else:
            image = image_data
        inputs = processor(image, return_tensors="pt")
        out = model.generate(**inputs, max_length=50)
        caption = processor.decode(out[0], skip_special_tokens=True)
        return caption
    
    @staticmethod
    def transcribe_audio(audio_data: bytes, language: str = None) -> Dict:
        """Transcribe audio using Whisper"""
        model = _load_whisper()
        if model is None:
            return {"text": "Whisper not available", "language": None}
        # Save audio to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name
        try:
            result = model.transcribe(tmp_path, language=language)
            return {"text": result["text"], "language": result["language"]}
        finally:
            os.unlink(tmp_path)
    
    @staticmethod
    def get_audio_embedding(audio_data: bytes) -> np.ndarray:
        """Get audio embedding (using Whisper encoder, simplified)"""
        # Whisper doesn't provide direct embedding easily; use transcribed text embedding as proxy
        trans = MultiModalService.transcribe_audio(audio_data)
        if trans["text"]:
            return MultiModalService.get_text_embedding(trans["text"])
        return np.zeros(512)
    
    @staticmethod
    def fuse_embeddings(embeddings: List[np.ndarray], weights: List[float] = None) -> np.ndarray:
        """Fuse multiple embeddings (e.g., vision + text + audio) via weighted average"""
        if weights is None:
            weights = [1.0 / len(embeddings)] * len(embeddings)
        fused = np.zeros_like(embeddings[0])
        for emb, w in zip(embeddings, weights):
            fused += emb * w
        return fused / np.linalg.norm(fused)  # L2 normalize

# Global instance
_mm_service = None
def get_mm_service():
    global _mm_service
    if _mm_service is None:
        _mm_service = MultiModalService()
    return _mm_service

# Import torch at runtime
try:
    import torch
except ImportError:
    torch = None
    print("PyTorch not installed – multi‑modal features limited")
