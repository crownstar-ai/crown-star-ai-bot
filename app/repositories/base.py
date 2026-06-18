from typing import TypeVar, Generic, Type, Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from app.core.database import Base

ModelType = TypeVar("ModelType", bound=Base)

class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session

    async def create(self, **kwargs) -> ModelType:
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.commit()
        await self.session.refresh(instance)
        return instance

    async def get_by_id(self, id: int) -> Optional[ModelType]:
        result = await self.session.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()

    async def update(self, id: int, **kwargs) -> Optional[ModelType]:
        await self.session.execute(update(self.model).where(self.model.id == id).values(**kwargs))
        await self.session.commit()
        return await self.get_by_id(id)

    async def delete(self, id: int) -> bool:
        await self.session.execute(delete(self.model).where(self.model.id == id))
        await self.session.commit()
        return True
