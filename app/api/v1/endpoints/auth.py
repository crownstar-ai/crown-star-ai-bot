from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db
from app.services.auth_service import AuthService
from app.api.v1.schemas.auth import LoginRequest, LoginResponse, RefreshTokenRequest

router = APIRouter()

@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    session: AsyncSession = Depends(get_db),
):
    auth_service = AuthService(session)
    user, access_token, refresh_token = await auth_service.authenticate(
        request.username, request.password
    )
    return LoginResponse(access_token=access_token, refresh_token=refresh_token)

@router.post("/refresh")
async def refresh(
    request: RefreshTokenRequest,
    session: AsyncSession = Depends(get_db),
):
    auth_service = AuthService(session)
    access_token, refresh_token = await auth_service.refresh_token(request.refresh_token)
    return {"access_token": access_token, "refresh_token": refresh_token}
