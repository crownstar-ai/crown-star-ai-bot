# datamasking/masking/mask_service.py – Data masking engine
import json
import re
from typing import Dict, Any, List, Optional
from ..pii.detector import get_pii_detector
from ..tokenisation.token_service import get_token_service
from ..policies.policy_loader import get_policy_loader

class MaskingService:
    def __init__(self):
        self.detector = get_pii_detector()
        self.token_service = get_token_service()
        self.policy_loader = get_policy_loader()
    
    def mask_field(self, value: str, field_type: str, mask_policy: str = "default", role: str = "user") -> str:
        """Apply masking policy to a single field"""
        policy = self.policy_loader.get_policy(field_type, mask_policy)
        if not policy:
            return value
        # Check role access
        if role in policy.get("viewer_roles", []):
            return value  # full access
        mask_type = policy.get("mask_type", "partial")
        if mask_type == "token":
            return self.token_service.tokenize(value, field_type)
        elif mask_type == "hash":
            import hashlib
            return hashlib.sha256(value.encode()).hexdigest()[:16]
        elif mask_type == "full":
            return "*" * len(value)
        elif mask_type == "partial":
            if len(value) <= 4:
                return "*" * len(value)
            return value[:2] + "*" * (len(value)-4) + value[-2:]
        elif mask_type == "redact":
            return "[REDACTED]"
        else:
            return value
    
    def mask_text(self, text: str, role: str = "user", preserve_tokens: bool = True) -> str:
        """Apply PII detection and mask according to policies"""
        # Detect PII
        detections = self.detector.detect(text)
        if not detections:
            return text
        # Process from end to start
        for det in reversed(detections):
            pii_type = det["type"]
            policy = self.policy_loader.get_policy(pii_type, "default")
            if not policy:
                continue
            if role in policy.get("viewer_roles", []):
                continue  # show original
            mask_type = policy.get("mask_type", "partial")
            if mask_type == "token" and preserve_tokens:
                token = self.token_service.tokenize(det["value"], pii_type)
                text = text[:det["start"]] + token + text[det["end"]:]
            elif mask_type == "hash":
                import hashlib
                masked = hashlib.sha256(det["value"].encode()).hexdigest()[:8]
                text = text[:det["start"]] + masked + text[det["end"]:]
            else:
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
                else:
                    continue
                text = text[:det["start"]] + masked + text[det["end"]:]
        return text
    
    def mask_dict(self, data: Dict, role: str = "user", field_mappings: Dict = None) -> Dict:
        """Mask dictionary recursively using field mappings"""
        result = {}
        for key, value in data.items():
            if field_mappings and key in field_mappings:
                field_type = field_mappings[key]
                if isinstance(value, str):
                    result[key] = self.mask_field(value, field_type, "default", role)
                elif isinstance(value, dict):
                    result[key] = self.mask_dict(value, role, field_mappings)
                elif isinstance(value, list):
                    result[key] = [self.mask_field(v, field_type, "default", role) if isinstance(v, str) else v for v in value]
                else:
                    result[key] = value
            elif isinstance(value, dict):
                result[key] = self.mask_dict(value, role, field_mappings)
            elif isinstance(value, str):
                result[key] = self.mask_text(value, role)
            else:
                result[key] = value
        return result

_mask_service = None
def get_mask_service():
    global _mask_service
    if _mask_service is None:
        _mask_service = MaskingService()
    return _mask_service
