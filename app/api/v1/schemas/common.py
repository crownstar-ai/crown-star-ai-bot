from pydantic import BaseModel
from typing import Optional, Any

class PaginationParams(BaseModel):
    page: int = 1
    page_size: int = 20

class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    total_pages: int

class ErrorResponse(BaseModel):
    detail: str
    code: Optional[str] = None
