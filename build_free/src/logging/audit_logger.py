# audit_logger.py – JSON structured logs with conversation timestamps
import json, logging
from datetime import datetime
from pathlib import Path

class ConversationAuditLogger:
    def __init__(self, log_dir: str = "data/logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.audit_file = self.log_dir / "conversation_audit.jsonl"
        self.json_logger = logging.getLogger("CrownStarAudit")
        handler = logging.FileHandler(self.audit_file, encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(message)s'))
        self.json_logger.addHandler(handler)
        self.json_logger.setLevel(logging.INFO)
        self.json_logger.propagate = False
    def log_conversation(self, user_id: str, user_msg: str, assistant_msg: str, tier: str, modules: list, latency_ms: int):
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "user_message": user_msg,
            "assistant_message": assistant_msg,
            "tier": tier,
            "active_modules": modules,
            "latency_ms": latency_ms,
            "version": "7.0.1"
        }
        self.json_logger.info(json.dumps(entry))
    def log_module_toggle(self, user_id: str, module: str, new_state: bool):
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "event": "module_toggle",
            "module": module,
            "state": new_state
        }
        self.json_logger.info(json.dumps(entry))
