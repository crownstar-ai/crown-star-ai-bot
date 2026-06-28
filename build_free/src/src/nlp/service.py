# nlp/service.py – Advanced NLP with Hugging Face transformers
import asyncio
import hashlib
import json
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import numpy as np

# Lazy imports to avoid heavy load at startup
_transformers_available = False
_sentence_transformers_available = False
_summarizer = None
_sentiment_analyzer = None
_embedder = None
_classifier = None

def _ensure_transformers():
    global _transformers_available, _summarizer, _sentiment_analyzer, _classifier
    if not _transformers_available:
        try:
            from transformers import pipeline
            _summarizer = pipeline("summarization", model="facebook/bart-large-cnn", device=-1)
            _sentiment_analyzer = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english", device=-1)
            _classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli", device=-1)
            _transformers_available = True
        except ImportError:
            print("Warning: transformers not installed. Install with: pip install transformers torch")
            _transformers_available = False

def _ensure_sentence_transformers():
    global _sentence_transformers_available, _embedder
    if not _sentence_transformers_available:
        try:
            from sentence_transformers import SentenceTransformer
            _embedder = SentenceTransformer('all-MiniLM-L6-v2')
            _sentence_transformers_available = True
        except ImportError:
            print("Warning: sentence-transformers not installed. Install with: pip install sentence-transformers")
            _sentence_transformers_available = False

class NLPService:
    @staticmethod
    async def summarize(text: str, max_length: int = 150, min_length: int = 30) -> str:
        """Summarise text using BART"""
        _ensure_transformers()
        if not _transformers_available:
            # Fallback: extract first few sentences
            sentences = text.split('.')[:3]
            return '. '.join(sentences) + ('...' if len(sentences) > 0 else '')
        if len(text) < 100:
            return text
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: _summarizer(text, max_length=max_length, min_length=min_length, do_sample=False))
        return result[0]['summary_text']
    
    @staticmethod
    async def analyze_sentiment(text: str) -> Dict:
        """Return sentiment label and confidence score"""
        _ensure_transformers()
        if not _transformers_available:
            # Simple rule‑based fallback
            positive_words = ['good', 'great', 'awesome', 'excellent', 'happy', 'love', 'wonderful']
            negative_words = ['bad', 'terrible', 'awful', 'sad', 'hate', 'disappointed', 'horrible']
            text_lower = text.lower()
            pos_count = sum(1 for w in positive_words if w in text_lower)
            neg_count = sum(1 for w in negative_words if w in text_lower)
            if pos_count > neg_count:
                return {"label": "POSITIVE", "score": 0.6 + (pos_count * 0.1)}
            elif neg_count > pos_count:
                return {"label": "NEGATIVE", "score": 0.6 + (neg_count * 0.1)}
            else:
                return {"label": "NEUTRAL", "score": 0.5}
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: _sentiment_analyzer(text[:512]))
        return {"label": result[0]['label'], "score": result[0]['score']}
    
    @staticmethod
    async def get_embedding(text: str) -> List[float]:
        """Return vector embedding (384‑dim) for semantic search"""
        _ensure_sentence_transformers()
        if not _sentence_transformers_available:
            # Fallback: simple hash embedding (not semantic, but deterministic)
            h = hashlib.sha256(text.encode()).digest()
            vec = [float(b) / 255.0 for b in h[:384]]
            return vec
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(None, lambda: _embedder.encode(text))
        return embedding.tolist()
    
    @staticmethod
    async def classify(text: str, candidate_labels: List[str]) -> Dict:
        """Zero‑shot classification"""
        _ensure_transformers()
        if not _transformers_available:
            # Fallback: simple keyword matching
            text_lower = text.lower()
            scores = {}
            for label in candidate_labels:
                score = 1.0 if label.lower() in text_lower else 0.0
                scores[label] = score
            # Normalise
            total = sum(scores.values())
            if total > 0:
                scores = {k: v/total for k,v in scores.items()}
            else:
                scores = {candidate_labels[0]: 1.0}
            return {"labels": candidate_labels, "scores": [scores.get(l,0) for l in candidate_labels]}
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: _classifier(text, candidate_labels))
        return {"labels": result['labels'], "scores": result['scores']}
    
    @staticmethod
    async def batch_summarize(texts: List[str], max_length: int = 150) -> List[str]:
        """Summarise multiple texts (batched)"""
        tasks = [NLPService.summarize(t, max_length) for t in texts]
        return await asyncio.gather(*tasks)
    
    @staticmethod
    async def batch_sentiment(texts: List[str]) -> List[Dict]:
        tasks = [NLPService.analyze_sentiment(t) for t in texts]
        return await asyncio.gather(*tasks)

# Global instance for easy import
nlp = NLPService()
