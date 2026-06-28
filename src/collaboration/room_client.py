# collaboration/room_client.py – Command‑line client for rooms
import asyncio
import websockets
import json
import sys
import threading
import time

class RoomClient:
    def __init__(self, uri="ws://localhost:8766"):
        self.uri = uri
        self.ws = None
        self.user_id = None
        self.room_id = None
        self.username = None
    
    async def connect(self, user_id, username, room_id):
        self.user_id = user_id
        self.username = username
        self.room_id = room_id
        self.ws = await websockets.connect(self.uri)
        await self.ws.send(json.dumps({
            "type": "auth",
            "user_id": user_id,
            "username": username,
            "room_id": room_id
        }))
        # Start receiver thread
        asyncio.create_task(self.receive())
        return True
    
    async def receive(self):
        try:
            async for msg in self.ws:
                data = json.loads(msg)
                msg_type = data.get("type")
                if msg_type == "message":
                    print(f"\n[{data.get('username')}]: {data.get('content')}")
                    if data.get("response"):
                        print(f"[CrownStar]: {data.get('response')}")
                elif msg_type == "system":
                    print(f"\n[System]: {data.get('content')}")
                elif msg_type == "typing":
                    if data.get("typing"):
                        print(f"\n[{data.get('username')} is typing...]")
                elif msg_type == "room_state":
                    print(f"\n[Room state: modules={data['state'].get('modules')}, tier={data['state'].get('tier')}]")
                elif msg_type == "state_updated":
                    print(f"\n[State updated by {data.get('by')}: {data.get('updates')}]")
        except:
            pass
    
    async def send_chat(self, text):
        await self.ws.send(json.dumps({
            "type": "chat",
            "query": text
        }))
    
    async def send_typing(self, is_typing):
        await self.ws.send(json.dumps({
            "type": "typing",
            "typing": is_typing
        }))
    
    async def update_state(self, updates):
        await self.ws.send(json.dumps({
            "type": "update_state",
            "updates": updates
        }))
    
    async def leave(self):
        await self.ws.send(json.dumps({"type": "leave"}))
        await self.ws.close()

async def interactive():
    import readline
    print("CrownStar Room Client")
    user_id = input("User ID (default: test_user): ").strip() or "test_user"
    username = input("Username: ").strip() or user_id
    room_id = input("Room ID (default: demo): ").strip() or "demo"
    client = RoomClient()
    await client.connect(user_id, username, room_id)
    print(f"Connected to room {room_id}. Type /help for commands.")
    
    # Input loop
    while True:
        try:
            inp = await asyncio.get_event_loop().run_in_executor(None, input, "> ")
            if not inp:
                continue
            if inp.startswith("/"):
                cmd = inp[1:].split()[0]
                if cmd == "quit" or cmd == "exit":
                    await client.leave()
                    break
                elif cmd == "state":
                    # Show current room state (would need API call)
                    print("State: use /update to change")
                elif cmd.startswith("update"):
                    # Usage: /update modules:ultra_super_model:true
                    print("Update command placeholder")
                else:
                    print("Commands: /quit, /update <key>=<value>")
            else:
                # Send typing indicator
                await client.send_typing(True)
                await asyncio.sleep(1)
                await client.send_chat(inp)
                await client.send_typing(False)
        except KeyboardInterrupt:
            await client.leave()
            break

if __name__ == "__main__":
    asyncio.run(interactive())
