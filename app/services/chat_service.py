from typing import List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.conversation import Conversation
from app.repositories.conversation_repo import ConversationRepository
from datetime import datetime

class ChatService:
    def __init__(self, session: AsyncSession):
        self.repo = ConversationRepository(session)

    async def save_conversation(
        self,
        user_id: int,
        messages: List[Dict[str, str]],
        response: str,
        model: str,
        tokens_used: int
    ) -> Conversation:
        conv = Conversation(
            user_id=user_id,
            messages=messages,
            response=response,
            model=model,
            tokens_used=tokens_used,
            created_at=datetime.utcnow()
        )
        return await self.repo.create(conv)
