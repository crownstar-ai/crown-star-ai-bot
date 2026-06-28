# analytics/websocket.py – WebSocket streaming for live dashboards
from fastapi import WebSocket, WebSocketDisconnect, APIRouter, Depends
from .core import get_monitor
from security.dependencies import require_permission
import asyncio
import json

router = APIRouter(prefix="/v1/analytics", tags=["Analytics"])

@router.websocket("/stream")
async def websocket_stream(websocket: WebSocket):
    """WebSocket endpoint for real‑time metric and anomaly streaming."""
    await websocket.accept()
    monitor = get_monitor()
    monitor.register_websocket_client(websocket)
    try:
        while True:
            # Keep connection alive, data sent by monitor's streaming loop
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        monitor.unregister_websocket_client(websocket)
