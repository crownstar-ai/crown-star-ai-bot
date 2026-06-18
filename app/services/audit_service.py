from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit_log import AuditLog
from app.repositories.audit_log_repo import AuditLogRepository

class AuditService:
    def __init__(self, session: AsyncSession):
        self.repo = AuditLogRepository(session)

    async def log(
        self,
        action: str,
        details: dict,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        log_entry = AuditLog(
            user_id=user_id,
            action=action,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent
        )
        await self.repo.create(log_entry)
