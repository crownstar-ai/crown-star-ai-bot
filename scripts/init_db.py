import asyncio
from app.core.database import db
from app.models import user, role, permission, conversation, audit_log
from app.core.database import Base

async def init():
    await db.initialize()
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created")
    await db.close()

if __name__ == "__main__":
    asyncio.run(init())
