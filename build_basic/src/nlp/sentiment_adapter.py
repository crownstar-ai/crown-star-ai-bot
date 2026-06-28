# nlp/sentiment_adapter.py – Adapt responses based on detected sentiment
from typing import Dict, Tuple

class SentimentAdapter:
    """Adjust assistant responses based on user sentiment"""
    
    @staticmethod
    def get_prefix(sentiment: Dict) -> str:
        label = sentiment.get('label', 'NEUTRAL')
        score = sentiment.get('score', 0.5)
        if label == 'POSITIVE' and score > 0.8:
            return "I'm glad you're feeling positive! "
        elif label == 'NEGATIVE' and score > 0.7:
            return "I understand this might be difficult. Let me help: "
        elif label == 'NEGATIVE':
            return "I hear your concern. Here's my response: "
        elif label == 'NEUTRAL':
            return ""
        else:
            return ""
    
    @staticmethod
    def adapt_response(original_response: str, sentiment: Dict) -> str:
        prefix = SentimentAdapter.get_prefix(sentiment)
        if prefix:
            return prefix + original_response
        return original_response
