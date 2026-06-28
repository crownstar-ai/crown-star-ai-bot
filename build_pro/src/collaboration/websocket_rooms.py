# collaboration/websocket_rooms.py – WebSocket server with room awareness
import asyncio
import json
import websockets
from websockets.exceptions import ConnectionClosed
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core'))
from crownstar_core import create_core
from .room_service import get_room_service

core = create_core()
room_service = get_room_service()

# Track connections: websocket -> {user_id, room_id, username}
connections = {}

async def broadcast_to_room(room_id: str, message: dict, exclude_ws=None):
    """Send message to all WebSocket clients in a room"""
    for ws, info in connections.items():
        if info.get("room_id") == room_id and ws != exclude_ws:
            try:
                await ws.send(json.dumps(message))
            except:
                pass

async def handler(websocket, path):
    user_id = None
    room_id = None
    username = None
    try:
        async for message in websocket:
            data = json.loads(message)
            msg_type = data.get("type", "unknown")
            
            if msg_type == "auth":
                # Authenticate and join room
                user_id = data.get("user_id", f"anon_{id(websocket)}")
                username = data.get("username", user_id[:8])
                room_id = data.get("room_id")
                if room_id:
                    room_info = room_service.get_room(room_id)
                    if not room_info:
                        # Auto‑create room if doesn't exist (for simplicity)
                        room_id = room_service.create_room(f"Room_{room_id}", user_id, False)
                    else:
                        room_service.join_room(room_id, user_id)
                    connections[websocket] = {"user_id": user_id, "room_id": room_id, "username": username}
                    # Send current room state and presence
                    shared_state = room_service.get_shared_state(room_id)
                    await websocket.send(json.dumps({
                        "type": "room_state",
                        "state": shared_state,
                        "presence": room_service.get_presence(room_id)
                    }))
                    # Broadcast join notification
                    await broadcast_to_room(room_id, {
                        "type": "system",
                        "content": f"{username} joined the room",
                        "timestamp": time.time()
                    }, exclude_ws=websocket)
            
            elif msg_type == "chat":
                user_id = connections.get(websocket, {}).get("user_id")
                room_id = connections.get(websocket, {}).get("room_id")
                username = connections.get(websocket, {}).get("username")
                if room_id and user_id:
                    query = data.get("query", "")
                    # Process through CrownStar core (respect room shared state)
                    room_state = room_service.get_shared_state(room_id)
                    # Apply room state (modules, tier, model)
                    for mod, enabled in room_state.get("modules", {}).items():
                        core.set_module(mod, enabled)
                    if "tier" in room_state:
                        core.set_tier(room_state["tier"])
                    if "model" in room_state:
                        core.set_model(room_state["model"])
                    # Generate response
                    response = core.answer_sync(query)
                    # Save message
                    room_service.save_message(room_id, user_id, username, query)
                    room_service.save_message(room_id, "crownstar", "CrownStar", response["answer"])
                    # Broadcast to room
                    await broadcast_to_room(room_id, {
                        "type": "message",
                        "user_id": user_id,
                        "username": username,
                        "content": query,
                        "response": response["answer"],
                        "timestamp": time.time()
                    })
            
            elif msg_type == "typing":
                user_id = connections.get(websocket, {}).get("user_id")
                room_id = connections.get(websocket, {}).get("room_id")
                if room_id and user_id:
                    is_typing = data.get("typing", False)
                    room_service.update_presence(room_id, user_id, typing=is_typing)
                    await broadcast_to_room(room_id, {
                        "type": "typing",
                        "user_id": user_id,
                        "username": username,
                        "typing": is_typing
                    }, exclude_ws=websocket)
            
            elif msg_type == "update_state":
                # Update shared room state (modules, tier, model)
                room_id = connections.get(websocket, {}).get("room_id")
                if room_id:
                    updates = data.get("updates", {})
                    room_service.update_shared_state(room_id, updates)
                    await broadcast_to_room(room_id, {
                        "type": "state_updated",
                        "updates": updates,
                        "by": connections.get(websocket, {}).get("username")
                    })
            
            elif msg_type == "leave":
                room_id = connections.get(websocket, {}).get("room_id")
                user_id = connections.get(websocket, {}).get("user_id")
                username = connections.get(websocket, {}).get("username")
                if room_id and user_id:
                    room_service.leave_room(room_id, user_id)
                    await broadcast_to_room(room_id, {
                        "type": "system",
                        "content": f"{username} left the room",
                        "timestamp": time.time()
                    })
                if websocket in connections:
                    del connections[websocket]
                break
    
    except ConnectionClosed:
        pass
    finally:
        # Cleanup
        if websocket in connections:
            info = connections[websocket]
            room_id = info.get("room_id")
            user_id = info.get("user_id")
            username = info.get("username")
            if room_id and user_id:
                room_service.leave_room(room_id, user_id)
                await broadcast_to_room(room_id, {
                    "type": "system",
                    "content": f"{username} disconnected",
                    "timestamp": time.time()
                })
            del connections[websocket]

async def start_room_server(port=8766):
    async with websockets.serve(handler, "0.0.0.0", port):
        print(f"✅ CrownStar Collaboration WebSocket server running on ws://0.0.0.0:{port}")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(start_room_server())
