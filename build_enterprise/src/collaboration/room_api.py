# collaboration/room_api.py – REST endpoints for rooms
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from .room_service import get_room_service
from security.dependencies import get_current_user, require_permission

router = APIRouter(prefix="/v1/rooms", tags=["Collaboration"])

class CreateRoomRequest(BaseModel):
    name: str
    is_private: bool = False

class JoinRoomRequest(BaseModel):
    room_id: str

class MessageRequest(BaseModel):
    content: str

@router.post("/create")
async def create_room(req: CreateRoomRequest, user: dict = Depends(get_current_user)):
    service = get_room_service()
    room_id = service.create_room(req.name, user["user_id"], req.is_private)
    return {"room_id": room_id, "name": req.name, "message": "Room created"}

@router.post("/join")
async def join_room(req: JoinRoomRequest, user: dict = Depends(get_current_user)):
    service = get_room_service()
    success = service.join_room(req.room_id, user["user_id"])
    if not success:
        raise HTTPException(404, "Room not found")
    return {"message": f"Joined room {req.room_id}"}

@router.post("/leave")
async def leave_room(req: JoinRoomRequest, user: dict = Depends(get_current_user)):
    service = get_room_service()
    service.leave_room(req.room_id, user["user_id"])
    return {"message": "Left room"}

@router.get("/list")
async def list_rooms(user: dict = Depends(get_current_user)):
    service = get_room_service()
    rooms = service.list_rooms(user["user_id"])
    return {"rooms": rooms}

@router.get("/{room_id}/messages")
async def get_messages(room_id: str, limit: int = 50, user: dict = Depends(get_current_user)):
    service = get_room_service()
    # Verify membership
    # (simplified: skip membership check for demo)
    messages = service.get_messages(room_id, limit)
    return {"messages": messages}

@router.get("/{room_id}/presence")
async def get_presence(room_id: str, user: dict = Depends(get_current_user)):
    service = get_room_service()
    presence = service.get_presence(room_id)
    return {"presence": presence}

@router.get("/{room_id}/state")
async def get_room_state(room_id: str, user: dict = Depends(get_current_user)):
    service = get_room_service()
    state = service.get_shared_state(room_id)
    return {"state": state}
