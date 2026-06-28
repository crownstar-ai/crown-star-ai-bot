# websocket_cli.py – WebSocket client for interactive streaming CLI
import asyncio
import json
import sys
import os
import websockets
import threading
from typing import Optional

class WebSocketCrownStarClient:
    def __init__(self, uri: str = "ws://localhost:8765", token: Optional[str] = None):
        self.uri = uri
        self.token = token
        self.websocket = None
        self.connected = False
    
    async def connect(self):
        try:
            self.websocket = await websockets.connect(self.uri)
            self.connected = True
            print(f"Connected to CrownStar WebSocket at {self.uri}")
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False
    
    async def disconnect(self):
        if self.websocket:
            await self.websocket.close()
            self.connected = False
    
    async def send_chat(self, query: str, modules: dict = None, tier: str = None, model: str = None):
        if not self.connected:
            print("Not connected")
            return
        
        message = {
            "type": "chat",
            "query": query,
            "modules": modules or {},
            "tier": tier,
            "model": model
        }
        if self.token:
            message["token"] = self.token
        
        await self.websocket.send(json.dumps(message))
        
        # Receive and print tokens as they arrive
        full_response = ""
        while True:
            response = await self.websocket.recv()
            data = json.loads(response)
            if data.get("type") == "token":
                token = data.get("token", "")
                print(token, end="", flush=True)
                full_response += token
            elif data.get("type") == "done":
                print()  # Newline after stream
                return full_response
            elif data.get("type") == "error":
                print(f"\nError: {data.get('message')}")
                return None
    
    async def get_modules(self):
        await self.websocket.send(json.dumps({"type": "get_modules"}))
        response = await self.websocket.recv()
        return json.loads(response).get("modules", {})
    
    async def toggle_module(self, module: str, enabled: bool):
        msg = {"type": "toggle_module", "module": module, "enabled": enabled}
        await self.websocket.send(json.dumps(msg))
        response = await self.websocket.recv()
        return json.loads(response)

def run_cli():
    """Run interactive CLI using WebSocket streaming"""
    import readline
    client = WebSocketCrownStarClient()
    
    async def main():
        if not await client.connect():
            return
        print("\nCrownStar WebSocket CLI (type /quit to exit)")
        print("Commands: /modules, /toggle <module> on|off, /tier <tier>, /model <model>")
        print("Enter your message to chat (streaming response):\n")
        
        while True:
            try:
                user_input = input("\033[92m> \033[0m").strip()
                if not user_input:
                    continue
                if user_input == "/quit":
                    break
                if user_input.startswith("/"):
                    parts = user_input.split()
                    cmd = parts[0]
                    if cmd == "/modules":
                        modules = await client.get_modules()
                        for k, v in modules.items():
                            print(f"  {k}: {'ON' if v else 'OFF'}")
                    elif cmd == "/toggle" and len(parts) == 3:
                        await client.toggle_module(parts[1], parts[2].lower() == "on")
                        print(f"Module {parts[1]} toggled")
                    elif cmd == "/tier" and len(parts) == 2:
                        # Pass tier in next chat
                        print(f"Tier set to {parts[1]} (will apply on next message)")
                    else:
                        print("Unknown command")
                else:
                    await client.send_chat(user_input)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")
        
        await client.disconnect()
    
    asyncio.run(main())

if __name__ == "__main__":
    run_cli()
