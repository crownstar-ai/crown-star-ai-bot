# ddd/entities/domain_entities.py – Core domain entities
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from ..entity import Entity
from ..value_object import UserId, ConversationId, Tier, ModelName, ModuleState, Money, Timestamp

@dataclass
class Conversation(Entity):
    id: ConversationId
    user_id: UserId
    tier: Tier
    messages: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    version: int = 1
    
    def _get_id(self):
        return self.id.value
    
    def add_message(self, user_message: str, assistant_message: str, modules_active: List[str], model: ModelName, latency_ms: int):
        self.messages.append({
            "user": user_message,
            "assistant": assistant_message,
            "modules": modules_active,
            "model": model.value,
            "latency_ms": latency_ms,
            "timestamp": datetime.utcnow().isoformat()
        })
        self.updated_at = datetime.utcnow()
        self.version += 1
    
    def change_tier(self, new_tier: Tier):
        self.tier = new_tier
        self.updated_at = datetime.utcnow()
        self.version += 1
    
    def message_count(self) -> int:
        return len(self.messages)
    
    def total_chars(self) -> int:
        input_chars = sum(len(m["user"]) for m in self.messages)
        output_chars = sum(len(m["assistant"]) for m in self.messages)
        return input_chars + output_chars

@dataclass
class User(Entity):
    id: UserId
    username: str
    email: str
    tier: Tier
    current_model: ModelName
    modules: Dict[str, bool] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_active: datetime = field(default_factory=datetime.utcnow)
    total_requests: int = 0
    total_cost: Money = field(default_factory=lambda: Money(0.0))
    
    def _get_id(self):
        return self.id.value
    
    def toggle_module(self, module_name: str, enabled: bool):
        self.modules[module_name] = enabled
        self.last_active = datetime.utcnow()
        self.version += 1
    
    def switch_model(self, model: ModelName):
        self.current_model = model
        self.last_active = datetime.utcnow()
        self.version += 1
    
    def change_tier(self, new_tier: Tier):
        self.tier = new_tier
        self.last_active = datetime.utcnow()
        self.version += 1
    
    def record_request(self, cost: Money):
        self.total_requests += 1
        self.total_cost = self.total_cost.add(cost)
        self.last_active = datetime.utcnow()
        self.version += 1

@dataclass
class ModuleConfiguration(Entity):
    """Global module configuration (singleton)"""
    id: str = "global_config"
    modules: Dict[str, bool] = field(default_factory=dict)
    version: int = 1
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def _get_id(self):
        return self.id
    
    def toggle_module(self, module_name: str, enabled: bool):
        self.modules[module_name] = enabled
        self.version += 1
        self.updated_at = datetime.utcnow()
    
    def is_enabled(self, module_name: str) -> bool:
        return self.modules.get(module_name, False)

@dataclass
class BillingRecord(Entity):
    id: str
    user_id: UserId
    amount: Money
    reason: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def _get_id(self):
        return self.id
