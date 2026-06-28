# ddd/value_object.py – Base class for value objects (immutable, structural equality)
from abc import ABC
from typing import Any, Dict, Tuple
from dataclasses import dataclass, asdict

class ValueObject(ABC):
    """Base class for value objects – immutable and compared by attributes"""
    
    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return self._attributes() == other._attributes()
    
    def __hash__(self) -> int:
        return hash(tuple(sorted(self._attributes().items())))
    
    def _attributes(self) -> Dict[str, Any]:
        """Return all attributes that define the value object's equality"""
        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}
    
    def __repr__(self) -> str:
        attrs = ", ".join(f"{k}={v!r}" for k, v in self._attributes().items())
        return f"{self.__class__.__name__}({attrs})"

# Example value objects
@dataclass(frozen=True)
class UserId(ValueObject):
    value: str
    
    def __post_init__(self):
        if not self.value:
            raise ValueError("UserId cannot be empty")
    
    @staticmethod
    def generate() -> 'UserId':
        import uuid
        return UserId(str(uuid.uuid4()))

@dataclass(frozen=True)
class ConversationId(ValueObject):
    value: str
    
    @staticmethod
    def generate() -> 'ConversationId':
        import uuid
        return ConversationId(str(uuid.uuid4()))

@dataclass(frozen=True)
class Tier(ValueObject):
    name: str
    allowed_values = {"free_pay_per_use", "basic", "pro", "enterprise"}
    
    def __post_init__(self):
        if self.name not in self.allowed_values:
            raise ValueError(f"Invalid tier: {self.name}")
    
    @staticmethod
    def free() -> 'Tier':
        return Tier("free_pay_per_use")
    
    @staticmethod
    def basic() -> 'Tier':
        return Tier("basic")
    
    @staticmethod
    def pro() -> 'Tier':
        return Tier("pro")
    
    @staticmethod
    def enterprise() -> 'Tier':
        return Tier("enterprise")

@dataclass(frozen=True)
class ModelName(ValueObject):
    value: str
    
    @staticmethod
    def deepseek_v2() -> 'ModelName':
        return ModelName("deepseek_v2_lite")
    
    @staticmethod
    def deepseek_v3() -> 'ModelName':
        return ModelName("deepseek_v3")

@dataclass(frozen=True)
class ModuleState(ValueObject):
    """Represents the enabled/disabled state of a single module"""
    name: str
    enabled: bool
    
    def toggle(self) -> 'ModuleState':
        return ModuleState(self.name, not self.enabled)

@dataclass(frozen=True)
class Money(ValueObject):
    amount: float
    currency: str = "USD"
    
    def __post_init__(self):
        if self.amount < 0:
            raise ValueError("Money amount cannot be negative")
    
    def add(self, other: 'Money') -> 'Money':
        if self.currency != other.currency:
            raise ValueError("Cannot add different currencies")
        return Money(self.amount + other.amount, self.currency)

@dataclass(frozen=True)
class Percentage(ValueObject):
    value: float  # 0.0 - 1.0
    
    def __post_init__(self):
        if not 0.0 <= self.value <= 1.0:
            raise ValueError(f"Percentage must be between 0 and 1: {self.value}")
    
    @staticmethod
    def of(percent: float) -> 'Percentage':
        return Percentage(percent / 100.0)
    
    def to_float(self) -> float:
        return self.value

@dataclass(frozen=True)
class Timestamp(ValueObject):
    value: datetime
    
    def __post_init__(self):
        if not isinstance(self.value, datetime):
            raise ValueError("Timestamp value must be datetime")
    
    @staticmethod
    def now() -> 'Timestamp':
        return Timestamp(datetime.utcnow())
    
    def isoformat(self) -> str:
        return self.value.isoformat()

from datetime import datetime
