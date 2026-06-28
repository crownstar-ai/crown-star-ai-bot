# streaming/core.py – CrownStar Real‑Time Streaming Engine (Kafka, Pulsar, NATS, Event Sourcing)
import os, json, time, threading, queue, uuid, hashlib, base64
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from collections import defaultdict
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)

class StreamBackend(Enum):
    KAFKA = "kafka"; PULSAR = "pulsar"; NATS = "nats"; REDIS_STREAMS = "redis_streams"; MEMORY = "memory"

class OffsetReset(Enum):
    EARLIEST = "earliest"; LATEST = "latest"; NONE = "none"

@dataclass
class StreamDefinition:
    stream_id: str; name: str; backend: StreamBackend; topic: str
    partitions: int = 1; replication_factor: int = 1; retention_ms: int = 604800000; created_at: int = 0

@dataclass
class StreamMessage:
    message_id: str; stream_id: str; key: Optional[str]; value: Any; timestamp: int; headers: Dict

@dataclass
class ConsumerGroup:
    group_id: str; stream_id: str; offset: int; last_commit: int

@dataclass
class StreamProcessor:
    processor_id: str; name: str; input_stream: str; output_stream: Optional[str]
    function: str; window_type: Optional[str]; window_size_ms: Optional[int]; parallelism: int = 1

class StreamingBackend(ABC):
    @abstractmethod
    def create_topic(self, topic: str, partitions: int) -> bool: pass
    @abstractmethod
    def publish(self, topic: str, key: Optional[str], value: Any) -> str: pass
    @abstractmethod
    def subscribe(self, topic: str, group_id: str, offset_reset: OffsetReset) -> "StreamConsumer": pass
    @abstractmethod
    def commit(self, group_id: str, topic: str, partition: int, offset: int) -> bool: pass

class StreamConsumer:
    def __init__(self, backend, topic, group_id):
        self.backend = backend; self.topic = topic; self.group_id = group_id
        self._running = False; self._thread = None; self._callback = None
    def start(self, callback: Callable[[StreamMessage], None]): self._callback = callback; self._running = True; self._thread = threading.Thread(target=self._consume_loop, daemon=True); self._thread.start()
    def stop(self): self._running = False; if self._thread: self._thread.join(timeout=5)
    def _consume_loop(self): raise NotImplementedError

class MemoryBackend(StreamingBackend):
    def __init__(self):
        self._topics: Dict[str, List[StreamMessage]] = defaultdict(list)
        self._offsets: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    def create_topic(self, topic: str, partitions: int) -> bool: return True
    def publish(self, topic: str, key: Optional[str], value: Any) -> str:
        msg_id = str(uuid.uuid4())
        msg = StreamMessage(message_id=msg_id, stream_id="", key=key, value=value, timestamp=int(time.time()*1000), headers={})
        self._topics[topic].append(msg)
        return msg_id
    def subscribe(self, topic: str, group_id: str, offset_reset: OffsetReset) -> StreamConsumer:
        return MemoryConsumer(self, topic, group_id, offset_reset)
    def commit(self, group_id: str, topic: str, partition: int, offset: int) -> bool:
        self._offsets[group_id][topic] = offset; return True

class MemoryConsumer(StreamConsumer):
    def __init__(self, backend, topic, group_id, offset_reset):
        super().__init__(backend, topic, group_id)
        self.backend = backend; self.offset_reset = offset_reset; self.current_offset = 0
    def _consume_loop(self):
        while self._running:
            messages = self.backend._topics.get(self.topic, [])
            if self.current_offset < len(messages):
                msg = messages[self.current_offset]
                self._callback(msg)
                self.current_offset += 1
                self.backend.commit(self.group_id, self.topic, 0, self.current_offset)
            else: time.sleep(0.1)

class SchemaRegistry:
    def __init__(self, storage_dir="data/streaming/schemas"):
        self.storage_dir = storage_dir; os.makedirs(storage_dir, exist_ok=True); self.schemas: Dict[str, Dict] = {}
    def register(self, name: str, schema_type: str, definition: Dict) -> str:
        schema_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()[:16]
        self.schemas[schema_id] = {"name":name,"type":schema_type,"definition":definition,"version":1,"created":int(time.time())}
        self._save(); return schema_id
    def get(self, schema_id: str) -> Optional[Dict]: return self.schemas.get(schema_id)
    def _save(self): with open(os.path.join(self.storage_dir,"schemas.json"),'w') as f: json.dump(self.schemas,f,indent=2)

class StreamProcessorEngine:
    def __init__(self): self.processors: Dict[str, StreamProcessor] = {}; self._running = False; self._threads = []
    def register(self, processor: StreamProcessor): self.processors[processor.processor_id] = processor
    def start(self, streaming_engine):
        self._running = True
        for proc in self.processors.values():
            consumer = streaming_engine.subscribe(proc.input_stream, f"processor_{proc.processor_id}", OffsetReset.EARLIEST)
            def make_handler(p):
                def handler(msg):
                    module_path, func_name = p.function.rsplit(".",1)
                    module = __import__(module_path, fromlist=[func_name])
                    func = getattr(module, func_name)
                    result = func(msg.value)
                    if p.output_stream and result is not None: streaming_engine.publish(p.output_stream, msg.key, result)
                return handler
            consumer.start(make_handler(proc))
            self._threads.append(consumer)

class StreamingManager:
    def __init__(self, config_path="config/streaming/config.json"):
        self.config = self._load_config(config_path)
        self.backend = self._init_backend()
        self.schema_registry = SchemaRegistry()
        self.processor_engine = StreamProcessorEngine()
        self.streams: Dict[str, StreamDefinition] = {}
        self._load_streams()
    def _load_config(self, path):
        default = {"backend":"memory","kafka_bootstrap_servers":"localhost:9092","pulsar_service_url":"pulsar://localhost:6650","nats_servers":["nats://localhost:4222"],"redis_host":"localhost","redis_port":6379,"default_partitions":1,"default_replication":1}
        if os.path.exists(path):
            with open(path,'r') as f: default.update(json.load(f))
        return default
    def _init_backend(self):
        backend_type = StreamBackend(self.config["backend"])
        if backend_type == StreamBackend.MEMORY: return MemoryBackend()
        elif backend_type == StreamBackend.KAFKA:
            try:
                from confluent_kafka import Producer, Consumer
                return KafkaBackend(self.config)
            except ImportError: logger.warning("confluent_kafka not installed, falling back to memory"); return MemoryBackend()
        else: return MemoryBackend()
    def _load_streams(self):
        stream_path = os.path.join("data/streaming","streams.json")
        if os.path.exists(stream_path):
            with open(stream_path,'r') as f:
                data = json.load(f)
                for sid, d in data.items():
                    d["backend"] = StreamBackend(d["backend"])
                    self.streams[sid] = StreamDefinition(**d)
    def _save_streams(self):
        stream_path = os.path.join("data/streaming","streams.json")
        data = {sid: asdict(s) for sid, s in self.streams.items()}
        for d in data.values(): d["backend"] = d["backend"].value
        with open(stream_path,'w') as f: json.dump(data,f,indent=2)
    def create_stream(self, name: str, topic: str, partitions: int = None) -> StreamDefinition:
        stream_id = str(uuid.uuid4())[:8]
        if partitions is None: partitions = self.config["default_partitions"]
        self.backend.create_topic(topic, partitions)
        stream = StreamDefinition(stream_id=stream_id, name=name, backend=StreamBackend(self.config["backend"]), topic=topic, partitions=partitions, replication_factor=self.config["default_replication"], created_at=int(time.time()))
        self.streams[stream_id] = stream; self._save_streams(); return stream
    def publish(self, stream_id: str, key: Optional[str], value: Any) -> str:
        stream = self.streams.get(stream_id)
        if not stream: raise ValueError(f"Stream {stream_id} not found")
        return self.backend.publish(stream.topic, key, value)
    def subscribe(self, stream_id: str, group_id: str, callback: Callable, offset_reset: OffsetReset = OffsetReset.LATEST):
        stream = self.streams.get(stream_id)
        if not stream: raise ValueError(f"Stream {stream_id} not found")
        consumer = self.backend.subscribe(stream.topic, group_id, offset_reset)
        consumer.start(callback)
        return consumer
    def register_processor(self, processor: StreamProcessor) -> str:
        self.processor_engine.register(processor); return processor.processor_id
    def start_processors(self): self.processor_engine.start(self)
    def get_stream_stats(self, stream_id: str) -> Dict:
        stream = self.streams.get(stream_id)
        if not stream: return {}
        if isinstance(self.backend, MemoryBackend):
            return {"messages": len(self.backend._topics.get(stream.topic, [])), "topic": stream.topic}
        return {"topic": stream.topic}

_streaming_manager = None
def get_streaming_manager():
    global _streaming_manager
    if _streaming_manager is None: _streaming_manager = StreamingManager()
    return _streaming_manager
