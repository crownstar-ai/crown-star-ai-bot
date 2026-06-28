# ddd/entity.py – Base class for domain entities
from abc import ABC
from typing import Any, TypeVar, Generic, Optional
from dataclasses import dataclass
import uuid

T = TypeVar('T', bound='Entity')

class Entity(ABC):
    """Base class for all domain entities"""
    
    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Entity):
            return NotImplemented
        return self.__class__ == other.__class__ and self._get_id() == other._get_id()
    
    def __hash__(self) -> int:
        return hash((self.__class__, self._get_id()))
    
    def _get_id(self) -> Any:
        """Override in subclass to return the identity field"""
        raise NotImplementedError
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self._get_id()})"

@dataclass(frozen=True)
class DomainEvent(ABC):
    """Domain event base class"""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_on: datetime = field(default_factory=datetime.utcnow)
    aggregate_id: str = ""
    aggregate_type: str = ""

import uuid
from datetime import datetime
from dataclasses import dataclass, field
