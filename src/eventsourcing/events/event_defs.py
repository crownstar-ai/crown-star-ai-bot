# eventsourcing/events/event_defs.py – Domain events
import json, uuid
from abc import ABC
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass

class DomainEvent(ABC):
    pass

@dataclass
class ConversationCreated:
    event_type = "conversation.created"
    def __init__(self, aggregate_id: str, user_id: str, tier: str):
        self.aggregate_id = aggregate_id
        self.aggregate_type = "conversation"
        self.timestamp = datetime.utcnow()
        self.version = 1
        self.event_id = str(uuid.uuid4())
        self.data = {"user_id": user_id, "tier": tier}

@dataclass
class MessageAdded:
    event_type = "conversation.message_added"
    def __init__(self, aggregate_id: str, user_message: str, assistant_message: str, modules_active: list, model: str, latency_ms: int):
        self.aggregate_id = aggregate_id
        self.aggregate_type = "conversation"
        self.timestamp = datetime.utcnow()
        self.version = 0
        self.event_id = str(uuid.uuid4())
        self.data = {
            "user_message": user_message,
            "assistant_message": assistant_message,
            "modules_active": modules_active,
            "model": model,
            "latency_ms": latency_ms
        }

@dataclass
class ModuleToggled:
    event_type = "module.toggled"
    def __init__(self, aggregate_id: str, module_name: str, new_state: bool):
        self.aggregate_id = aggregate_id
        self.aggregate_type = "configuration"
        self.timestamp = datetime.utcnow()
        self.version = 0
        self.event_id = str(uuid.uuid4())
        self.data = {"module": module_name, "enabled": new_state}

@dataclass
class TierChanged:
    event_type = "tier.changed"
    def __init__(self, aggregate_id: str, new_tier: str):
        self.aggregate_id = aggregate_id
        self.aggregate_type = "configuration"
        self.timestamp = datetime.utcnow()
        self.version = 0
        self.event_id = str(uuid.uuid4())
        self.data = {"tier": new_tier}

@dataclass
class ModelSwitched:
    event_type = "model.switched"
    def __init__(self, aggregate_id: str, new_model: str):
        self.aggregate_id = aggregate_id
        self.aggregate_type = "configuration"
        self.timestamp = datetime.utcnow()
        self.version = 0
        self.event_id = str(uuid.uuid4())
        self.data = {"model": new_model}

def event_from_dict(data: dict):
    et = data.get("event_type")
    if et == "conversation.created":
        return ConversationCreated(data["aggregate_id"], data["data"]["user_id"], data["data"]["tier"])
    elif et == "conversation.message_added":
        return MessageAdded(data["aggregate_id"], data["data"]["user_message"], data["data"]["assistant_message"], data["data"]["modules_active"], data["data"]["model"], data["data"]["latency_ms"])
    elif et == "module.toggled":
        return ModuleToggled(data["aggregate_id"], data["data"]["module"], data["data"]["enabled"])
    elif et == "tier.changed":
        return TierChanged(data["aggregate_id"], data["data"]["tier"])
    elif et == "model.switched":
        return ModelSwitched(data["aggregate_id"], data["data"]["model"])
    else:
        raise ValueError(f"Unknown event type: {et}")
