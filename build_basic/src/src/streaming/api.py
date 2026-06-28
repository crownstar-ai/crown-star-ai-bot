# streaming/api.py – REST API for real‑time streaming
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from dataclasses import asdict
from .core import get_streaming_manager, StreamDefinition, StreamProcessor, OffsetReset
from security.dependencies import require_permission
import asyncio, threading

router = APIRouter(prefix="/v1/streams", tags=["Real‑Time Streaming"])

class CreateStreamRequest(BaseModel):
    name: str; topic: str; partitions: Optional[int] = None

class PublishRequest(BaseModel):
    stream_id: str; key: Optional[str] = None; value: Any

class SubscribeRequest(BaseModel):
    stream_id: str; group_id: str; offset_reset: str = "latest"

class ProcessorRequest(BaseModel):
    name: str; input_stream: str; output_stream: Optional[str] = None
    function: str; window_type: Optional[str] = None; window_size_ms: Optional[int] = None; parallelism: int = 1

@router.post("/streams")
async def create_stream(req: CreateStreamRequest, user=Depends(require_permission("admin"))):
    mgr = get_streaming_manager()
    stream = mgr.create_stream(req.name, req.topic, req.partitions)
    return {"stream_id": stream.stream_id, "topic": stream.topic}

@router.get("/streams")
async def list_streams(user=Depends(require_permission("admin"))):
    mgr = get_streaming_manager()
    return {"streams": [asdict(s) for s in mgr.streams.values()]}

@router.post("/publish")
async def publish_message(req: PublishRequest, user=Depends(require_permission("admin"))):
    mgr = get_streaming_manager()
    try:
        msg_id = mgr.publish(req.stream_id, req.key, req.value)
        return {"message_id": msg_id}
    except ValueError as e: raise HTTPException(404, str(e))

@router.websocket("/subscribe/{stream_id}/{group_id}")
async def websocket_subscribe(websocket: WebSocket, stream_id: str, group_id: str):
    await websocket.accept()
    mgr = get_streaming_manager()
    async def callback(msg):
        await websocket.send_json({"message_id": msg.message_id, "key": msg.key, "value": msg.value, "timestamp": msg.timestamp})
    def consume():
        mgr.subscribe(stream_id, group_id, lambda m: asyncio.run_coroutine_threadsafe(callback(m), asyncio.get_event_loop()))
    threading.Thread(target=consume, daemon=True).start()
    try:
        while True: await websocket.receive_text()
    except WebSocketDisconnect: pass

@router.post("/processors")
async def register_processor(req: ProcessorRequest, user=Depends(require_permission("admin"))):
    mgr = get_streaming_manager()
    import uuid
    proc_id = str(uuid.uuid4())[:8]
    processor = StreamProcessor(processor_id=proc_id, name=req.name, input_stream=req.input_stream, output_stream=req.output_stream, function=req.function, window_type=req.window_type, window_size_ms=req.window_size_ms, parallelism=req.parallelism)
    mgr.register_processor(processor)
    return {"processor_id": proc_id}

@router.get("/stats/{stream_id}")
async def stream_stats(stream_id: str, user=Depends(require_permission("admin"))):
    mgr = get_streaming_manager()
    stats = mgr.get_stream_stats(stream_id)
    if not stats: raise HTTPException(404, "Stream not found")
    return stats
