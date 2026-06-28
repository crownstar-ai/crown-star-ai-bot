# gateway/websocket/gateway.py – Unified WebSocket gateway
import asyncio
import json
import websockets
from websockets.exceptions import ConnectionClosed
from typing import Dict, Set, Optional
import uuid
import logging

logger = logging.getLogger("crownstar.ws.gateway")

# Backend WebSocket URLs
BACKENDS = {
    "chat": "ws://localhost:8765",
    "room": "ws://localhost:8766",
    "inference": "ws://localhost:8767",
    "monitoring": "ws://localhost:8768"
}

class WebSocketGateway:
    def __init__(self):
        self.connections: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.backend_connections: Dict[str, websockets.WebSocketClientProtocol] = {}
        self.routing_table: Dict[str, str] = {}  # client_id -> backend_type
    
    async def handle_client(self, websocket, path):
        client_id = str(uuid.uuid4())
        self.connections[client_id] = websocket
        logger.info(f"Client {client_id} connected")
        try:
            async for message in websocket:
                data = json.loads(message)
                msg_type = data.get("type", "unknown")
                if msg_type == "subscribe":
                    backend = data.get("backend", "chat")
                    if backend in BACKENDS:
                        # Establish connection to backend if not already open
                        if backend not in self.backend_connections:
                            backend_ws = await websockets.connect(BACKENDS[backend])
                            self.backend_connections[backend] = backend_ws
                            # Start forwarding from backend to all subscribed clients
                            asyncio.create_task(self._forward_backend(backend, backend_ws))
                        self.routing_table[client_id] = backend
                        await websocket.send(json.dumps({"type": "subscribed", "backend": backend}))
                    else:
                        await websocket.send(json.dumps({"type": "error", "message": f"Unknown backend: {backend}"}))
                elif msg_type == "message":
                    # Forward to subscribed backend
                    backend = self.routing_table.get(client_id)
                    if backend and backend in self.backend_connections:
                        await self.backend_connections[backend].send(message)
                    else:
                        await websocket.send(json.dumps({"type": "error", "message": "Not subscribed to any backend"}))
                elif msg_type == "unsubscribe":
                    backend = self.routing_table.pop(client_id, None)
                    await websocket.send(json.dumps({"type": "unsubscribed"}))
        except ConnectionClosed:
            pass
        finally:
            del self.connections[client_id]
            # Clean up backend connection if no clients left
            for backend, conn in list(self.backend_connections.items()):
                if not any(backend == self.routing_table.get(cid) for cid in self.connections):
                    await conn.close()
                    del self.backend_connections[backend]
            logger.info(f"Client {client_id} disconnected")
    
    async def _forward_backend(self, backend: str, backend_ws):
        try:
            async for message in backend_ws:
                # Broadcast to all clients subscribed to this backend
                for client_id, b in list(self.routing_table.items()):
                    if b == backend and client_id in self.connections:
                        try:
                            await self.connections[client_id].send(message)
                        except:
                            pass
        except:
            pass

_ws_gateway = None
async def start_ws_gateway(port=8769):
    global _ws_gateway
    _ws_gateway = WebSocketGateway()
    async with websockets.serve(_ws_gateway.handle_client, "0.0.0.0", port):
        logger.info(f"WebSocket gateway listening on ws://0.0.0.0:{port}")
        await asyncio.Future()
