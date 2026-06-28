# websocket_stream_server.py – Full WebSocket streaming server with token-by-token output
import asyncio
import json
import sys
import os
import hashlib
import time
from typing import Set, Dict
import websockets
from websockets.exceptions import ConnectionClosed

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core'))
from crownstar_core import create_core

# Configuration
WS_PORT = int(os.environ.get("WS_PORT", 8765))
AUTH_REQUIRED = os.environ.get("WS_AUTH", "false").lower() == "true"
VALID_TOKENS = set(os.environ.get("WS_TOKENS", "").split(",")) if AUTH_REQUIRED else set()

class CrownStarWebSocketServer:
    def __init__(self):
        self.core = create_core()
        self.active_connections: Set[websockets.WebSocketServerProtocol] = set()
        self.connection_metadata: Dict[websockets.WebSocketServerProtocol, dict] = {}
    
    async def authenticate(self, websocket, message: dict) -> bool:
        if not AUTH_REQUIRED:
            return True
        token = message.get("token", "")
        return token in VALID_TOKENS
    
    async def stream_response(self, websocket, query: str, modules: dict, tier: str = None, model: str = None):
        """Stream token-by-token response to client"""
        # Apply modules and tier
        if tier:
            self.core.set_tier(tier)
        for mod, enabled in modules.items():
            self.core.set_module(mod, enabled)
        if model:
            self.core.set_model(model)
        
        # Build prompt with module preprocessing
        active = self.core.modules.get_active()
        prompt = self.core.modules.apply_preprocessing(f"User: {query}\nAssistant:", query)
        
        # Call LLM and stream tokens (simulate token streaming for any LLM)
        # For real streaming, we would need token-by-token from each adapter
        # Here we simulate by splitting the final response
        full_response = await self.core._call_lm(prompt)
        # Also apply postprocessing
        final = self.core.modules.apply_postprocessing(full_response)
        
        # Send tokens one by one
        words = final.split()
        for i, word in enumerate(words):
            await websocket.send(json.dumps({
                "type": "token",
                "token": word + (" " if i < len(words)-1 else ""),
                "index": i,
                "total": len(words)
            }))
            await asyncio.sleep(0.03)  # Natural typing speed
        
        # Send completion message
        await websocket.send(json.dumps({
            "type": "done",
            "full_response": final,
            "token_count": len(words)
        }))
    
    async def handler(self, websocket, path):
        """Main WebSocket handler"""
        try:
            # Register connection
            self.active_connections.add(websocket)
            print(f"WebSocket client connected: {websocket.remote_address} (Total: {len(self.active_connections)})")
            
            async for message in websocket:
                try:
                    data = json.loads(message)
                    msg_type = data.get("type", "chat")
                    
                    if msg_type == "chat":
                        # Streaming chat request
                        query = data.get("query", "")
                        modules = data.get("modules", {})
                        tier = data.get("tier", None)
                        model = data.get("model", None)
                        
                        await self.stream_response(websocket, query, modules, tier, model)
                    
                    elif msg_type == "ping":
                        await websocket.send(json.dumps({"type": "pong", "timestamp": time.time()}))
                    
                    elif msg_type == "get_modules":
                        await websocket.send(json.dumps({
                            "type": "modules",
                            "modules": self.core.modules.modules_state
                        }))
                    
                    elif msg_type == "toggle_module":
                        mod = data.get("module")
                        enabled = data.get("enabled")
                        self.core.set_module(mod, enabled)
                        await websocket.send(json.dumps({
                            "type": "module_toggled",
                            "module": mod,
                            "enabled": enabled
                        }))
                    
                    elif msg_type == "set_tier":
                        tier = data.get("tier")
                        self.core.set_tier(tier)
                        await websocket.send(json.dumps({
                            "type": "tier_set",
                            "tier": tier
                        }))
                    
                    elif msg_type == "list_models":
                        models = self.core.model_router.list_models()
                        await websocket.send(json.dumps({
                            "type": "model_list",
                            "models": models
                        }))
                    
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({"type": "error", "message": "Invalid JSON"}))
                except Exception as e:
                    await websocket.send(json.dumps({"type": "error", "message": str(e)}))
        
        except ConnectionClosed:
            pass
        finally:
            self.active_connections.remove(websocket)
            print(f"WebSocket client disconnected: {websocket.remote_address} (Total: {len(self.active_connections)})")
    
    async def start(self):
        async with websockets.serve(self.handler, "0.0.0.0", WS_PORT, compression=None):
            print(f"✅ CrownStar WebSocket server running on ws://0.0.0.0:{WS_PORT}")
            print(f"   Active connections: {len(self.active_connections)}")
            await asyncio.Future()  # Run forever

if __name__ == "__main__":
    server = CrownStarWebSocketServer()
    asyncio.run(server.start())
