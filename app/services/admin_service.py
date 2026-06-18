from sqlalchemy.ext.asyncio import AsyncSession

class AdminService:
    def __init__(self, session: AsyncSession):
        self.session = session
    # Add admin methods as needed
