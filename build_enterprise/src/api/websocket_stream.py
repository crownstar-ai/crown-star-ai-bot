# websocket_stream.py – WebSocket server for real‑time token streaming
import asyncio, json, websockets, sys
sys.path.insert(0, "src/core")
from crownstar_core import create_core

core = create_core()

async def stream_handler(websocket, path):
    async for message in websocket:
        data = json.loads(message)
        query = data.get("query", "")
        full_response = core.answer_sync(query)
        tokens = full_response.split()
        for token in tokens:
            await websocket.send(json.dumps({"token": token + " ", "done": False}))
            await asyncio.sleep(0.05)
        await websocket.send(json.dumps({"token": "", "done": True}))

async def main():
    async with websockets.serve(stream_handler, "0.0.0.0", 8765):
        print("WebSocket streaming server running on ws://0.0.0.0:8765")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
