from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.user_repo import UserRepository
from app.models.user import User
from app.core.security import get_password_hash

class UserService:
    def __init__(self, session: AsyncSession):
        self.repo = UserRepository(session)

    async def get_by_id(self, user_id: int) -> Optional[User]:
        return await self.repo.get_by_id(user_id)

    async def update_user(self, user_id: int, **kwargs) -> Optional[User]:
        if "password" in kwargs:
            kwargs["hashed_password"] = get_password_hash(kwargs.pop("password"))
        return await self.repo.update(user_id, **kwargs)
