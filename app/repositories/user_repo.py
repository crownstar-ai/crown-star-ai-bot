from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from app.models.user import User
from app.repositories.base import BaseRepository

class UserRepository(BaseRepository[User]):
    def __init__(self, session: AsyncSession):
        super().__init__(User, session)

    async def get_by_username_or_email(self, username_or_email: str) -> Optional[User]:
        result = await self.session.execute(
            select(User).where(
                or_(User.username == username_or_email, User.email == username_or_email)
            )
        )
        return result.scalar_one_or_none()
