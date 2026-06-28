# eventsourcing/aggregates/conversation_aggregate.py – Aggregates
from typing import List
from ..events.event_defs import ConversationCreated, MessageAdded, ModuleToggled, TierChanged, ModelSwitched

class ConversationAggregate:
    def __init__(self, aggregate_id: str):
        self.id = aggregate_id
        self.user_id = None
        self.tier = None
        self.messages = []
        self.version = 0
        self._uncommitted_events = []
    
    @staticmethod
    def create(aggregate_id: str, user_id: str, tier: str):
        agg = ConversationAggregate(aggregate_id)
        event = ConversationCreated(aggregate_id, user_id, tier)
        agg._apply(event)
        agg._uncommitted_events.append(event)
        return agg
    
    def add_message(self, user_msg: str, assistant_msg: str, modules: list, model: str, latency_ms: int):
        event = MessageAdded(self.id, user_msg, assistant_msg, modules, model, latency_ms)
        event.version = self.version + 1
        self._apply(event)
        self._uncommitted_events.append(event)
    
    def _apply(self, event):
        if event.event_type == "conversation.created":
            self.user_id = event.data["user_id"]
            self.tier = event.data["tier"]
            self.version = 1
        elif event.event_type == "conversation.message_added":
            self.messages.append({
                "user": event.data["user_message"],
                "assistant": event.data["assistant_message"],
                "modules": event.data["modules_active"],
                "model": event.data["model"],
                "latency_ms": event.data["latency_ms"],
                "timestamp": event.timestamp.isoformat()
            })
            self.version = event.version
    
    def load_from_events(self, events):
        for e in events:
            self._apply(e)
        self._uncommitted_events = []
    
    def get_uncommitted_events(self):
        return self._uncommitted_events
    
    def mark_committed(self):
        self._uncommitted_events = []
    
    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "tier": self.tier,
            "messages_count": len(self.messages),
            "messages": self.messages[-10:],
            "version": self.version
        }

class ConfigurationAggregate:
    def __init__(self, aggregate_id: str = "global_config"):
        self.id = aggregate_id
        self.modules = {}
        self.tier = "free_pay_per_use"
        self.model = "deepseek_v2_lite"
        self.version = 0
        self._uncommitted_events = []
    
    def toggle_module(self, module: str, enabled: bool):
        event = ModuleToggled(self.id, module, enabled)
        event.version = self.version + 1
        self._apply(event)
        self._uncommitted_events.append(event)
    
    def change_tier(self, new_tier: str):
        event = TierChanged(self.id, new_tier)
        event.version = self.version + 1
        self._apply(event)
        self._uncommitted_events.append(event)
    
    def switch_model(self, new_model: str):
        event = ModelSwitched(self.id, new_model)
        event.version = self.version + 1
        self._apply(event)
        self._uncommitted_events.append(event)
    
    def _apply(self, event):
        if event.event_type == "module.toggled":
            self.modules[event.data["module"]] = event.data["enabled"]
            self.version = event.version
        elif event.event_type == "tier.changed":
            self.tier = event.data["tier"]
            self.version = event.version
        elif event.event_type == "model.switched":
            self.model = event.data["model"]
            self.version = event.version
    
    def load_from_events(self, events):
        for e in events:
            self._apply(e)
        self._uncommitted_events = []
    
    def get_uncommitted_events(self):
        return self._uncommitted_events
    
    def mark_committed(self):
        self._uncommitted_events = []
    
    def to_dict(self):
        return {
            "id": self.id,
            "modules": self.modules,
            "tier": self.tier,
            "model": self.model,
            "version": self.version
        }
