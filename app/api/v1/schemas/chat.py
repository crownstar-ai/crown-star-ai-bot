from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class Message(BaseModel):
    role: str  # "user", "assistant", "system"
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]
    model: Optional[str] = None
    temperature: float = 1.0
    top_p: float = 1.0
    max_tokens: Optional[int] = None
    system_prompt: Optional[str] = None
    thinking: bool = True
    reasoning_effort: str = "high"

class ChatStreamRequest(ChatRequest):
    pass

class ChatResponse(BaseModel):
    id: str
    model: str
    content: str
    usage: Dict[str, int]
    finish_reason: str
    conversation_id: int

class ConversationResponse(BaseModel):
    id: int
    messages: List[Dict[str, str]]
    response: str
    model: str
    tokens_used: int
    created_at: datetime
