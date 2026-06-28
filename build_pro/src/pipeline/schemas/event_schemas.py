# pipeline/schemas/event_schemas.py – Event definitions for pipeline
import json
import uuid
import time
from datetime import datetime
from typing import Dict, Any, Optional

class CrownStarEvent:
    @staticmethod
    def user_action(user_id: str, tenant_id: str, action: str, metadata: Dict = None) -> Dict:
        return {
            "event_id": str(uuid.uuid4()),
            "event_type": "user_action",
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "tenant_id": tenant_id,
            "action": action,
            "metadata": metadata or {}
        }
    
    @staticmethod
    def model_inference(user_id: str, model: str, input_chars: int, output_chars: int, latency_ms: int, cost: float) -> Dict:
        return {
            "event_id": str(uuid.uuid4()),
            "event_type": "model_inference",
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "model": model,
            "input_chars": input_chars,
            "output_chars": output_chars,
            "latency_ms": latency_ms,
            "cost": cost
        }
    
    @staticmethod
    def cost_event(user_id: str, tenant_id: str, amount: float, reason: str) -> Dict:
        return {
            "event_id": str(uuid.uuid4()),
            "event_type": "cost",
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "tenant_id": tenant_id,
            "amount": amount,
            "reason": reason
        }
    
    @staticmethod
    def conversation_event(conversation_id: str, user_id: str, tenant_id: str, message_count: int) -> Dict:
        return {
            "event_id": str(uuid.uuid4()),
            "event_type": "conversation",
            "timestamp": datetime.utcnow().isoformat(),
            "conversation_id": conversation_id,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "message_count": message_count
        }
    
    @staticmethod
    def alert(severity: str, source: str, message: str) -> Dict:
        return {
            "event_id": str(uuid.uuid4()),
            "event_type": "alert",
            "timestamp": datetime.utcnow().isoformat(),
            "severity": severity,
            "source": source,
            "message": message
        }
