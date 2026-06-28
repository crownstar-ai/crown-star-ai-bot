# datamasking/pii/detector.py – Detect PII in text
import re
import json
from typing import List, Dict, Tuple
from pathlib import Path

class PIIDetector:
    def __init__(self, patterns_path: str = "config/masking/pii_patterns.json"):
        self.patterns = self._load_patterns(patterns_path)
    
    def _load_patterns(self, path):
        default = {
            "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            "phone_us": r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
            "phone_international": r'\+\d{1,3}\s?\d{1,14}',
            "ssn": r'\b\d{3}-\d{2}-\d{4}\b',
            "credit_card": r'\b(?:\d[ -]*?){13,16}\b',
            "ipv4": r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b',
            "driver_license": r'\b[A-Z]{1,2}\d{6,8}\b',
            "date_of_birth": r'\b\d{4}-\d{2}-\d{2}\b|\b\d{2}/\d{2}/\d{4}\b',
            "address": r'\b\d{1,5}\s\w+\s(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr)\b',
            "name": r'\b(?:Mr\.|Mrs\.|Ms\.|Dr\.)?\s?[A-Z][a-z]+ [A-Z][a-z]+\b'
        }
        if Path(path).exists():
            with open(path, 'r') as f:
                user = json.load(f)
                default.update(user)
        return default
    
    def detect(self, text: str) -> List[Dict]:
        """Return list of detected PII with type, span, value"""
        results = []
        for pii_type, pattern in self.patterns.items():
            for match in re.finditer(pattern, text, re.IGNORECASE):
                results.append({
                    "type": pii_type,
                    "start": match.start(),
                    "end": match.end(),
                    "value": match.group(0),
                    "confidence": 0.9 if len(match.group(0)) > 3 else 0.7
                })
        # Sort by start position
        results.sort(key=lambda x: x["start"])
        return results
    
    def mask_by_type(self, text: str, mask_type: str = "partial") -> str:
        """Mask all detected PII in text"""
        detections = self.detect(text)
        # Process from end to start to preserve indices
        for det in reversed(detections):
            value = det["value"]
            if mask_type == "full":
                masked = "*" * len(value)
            elif mask_type == "partial":
                if len(value) <= 4:
                    masked = "*" * len(value)
                else:
                    masked = value[:2] + "*" * (len(value)-4) + value[-2:]
            elif mask_type == "redact":
                masked = "[REDACTED]"
            elif mask_type == "hash":
                import hashlib
                masked = hashlib.md5(value.encode()).hexdigest()[:8]
            else:
                masked = "[PII]"
            text = text[:det["start"]] + masked + text[det["end"]:]
        return text
    
    def anonymise_text(self, text: str, keep_first_last: bool = True) -> str:
        """Anonymise names (simple replacement)"""
        # Replace names with generic placeholders
        name_pattern = self.patterns.get("name", r'\b[A-Z][a-z]+ [A-Z][a-z]+\b')
        names = re.findall(name_pattern, text)
        name_counter = 1
        for name in set(names):
            text = text.replace(name, f"[NAME_{name_counter}]")
            name_counter += 1
        return text

_pii_detector = None
def get_pii_detector():
    global _pii_detector
    if _pii_detector is None:
        _pii_detector = PIIDetector()
    return _pii_detector
