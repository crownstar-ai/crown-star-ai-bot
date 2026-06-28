# canvas/websocket.py – WebSocket endpoint for live canvas collaboration
from fastapi import WebSocket, WebSocketDisconnect, APIRouter
from .core import get_canvas_manager
from dataclasses import asdict
import json

router = APIRouter()

@router.websocket("/ws/canvas/{canvas_id}")
async def canvas_websocket(websocket: WebSocket, canvas_id: str):
    await websocket.accept()
    mgr = get_canvas_manager()
    mgr.collab.join_room(canvas_id, websocket)
    try:
        state = mgr.get_canvas(canvas_id)
        if state:
            await websocket.send_json({"type": "init", "state": asdict(state)})
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg["type"] == "stroke":
                from .core import CanvasStroke
                stroke = CanvasStroke(**msg["stroke"])
                mgr.add_stroke(canvas_id, stroke)
            elif msg["type"] == "undo":
                mgr.undo(canvas_id)
            elif msg["type"] == "generate":
                prompt = msg.get("prompt", "")
                new_state = mgr.generate_from_text(prompt, state.width, state.height)
                mgr._save_state(new_state)
                mgr.collab.broadcast(canvas_id, {"type": "replace", "state": asdict(new_state)})
    except WebSocketDisconnect:
        mgr.collab.leave_room(canvas_id, websocket)
