from fastapi import APIRouter, Depends
from app.api.deps import get_current_superuser

router = APIRouter()

@router.get("/dashboard")
async def admin_dashboard(
    current_superuser = Depends(get_current_superuser)
):
    return {"message": "Admin dashboard"}
