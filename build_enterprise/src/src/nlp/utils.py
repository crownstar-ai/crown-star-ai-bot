# nlp/utils.py – Helper functions
import re
from collections import Counter
from typing import List, Dict

class NLPUtils:
    @staticmethod
    def extract_keywords(text: str, top_k: int = 5) -> List[str]:
        """Simple keyword extraction using TF‑IDF like frequency"""
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        stopwords = {'the','and','for','that','this','with','from','have','are','was','were','but','not','you','your','can','will','just'}
        filtered = [w for w in words if w not in stopwords]
        counter = Counter(filtered)
        return [word for word, count in counter.most_common(top_k)]
    
    @staticmethod
    def estimate_reading_time(text: str, wpm: int = 200) -> int:
        """Estimate reading time in seconds"""
        word_count = len(text.split())
        return int((word_count / wpm) * 60)
    
    @staticmethod
    def split_into_chunks(text: str, max_chars: int = 1000) -> List[str]:
        """Split long text into chunks for summarization"""
        if len(text) <= max_chars:
            return [text]
        chunks = []
        current = ""
        for sentence in text.split('. '):
            if len(current) + len(sentence) + 2 <= max_chars:
                current += sentence + '. '
            else:
                chunks.append(current.strip())
                current = sentence + '. '
        if current:
            chunks.append(current.strip())
        return chunks
    
    @staticmethod
    def detect_language(text: str) -> str:
        """Simple language detection (very basic)"""
        # Unicode ranges: Cyrillic, CJK, Arabic, etc.
        if re.search(r'[\u4e00-\u9fff]', text):
            return 'zh'
        elif re.search(r'[\u0400-\u04FF]', text):
            return 'ru'
        elif re.search(r'[\u0600-\u06FF]', text):
            return 'ar'
        elif re.search(r'[áéíóúñ]', text):
            return 'es'
        else:
            return 'en'
