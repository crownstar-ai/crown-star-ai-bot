# tracing/core.py – CrownStar Global Observability & Distributed Tracing Engine
import os, json, time, uuid, hashlib, threading, queue
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from contextvars import ContextVar
import logging

logger = logging.getLogger(__name__)

class SpanKind(Enum):
    INTERNAL = "internal"; SERVER = "server"; CLIENT = "client"
    PRODUCER = "producer"; CONSUMER = "consumer"

class SpanStatus(Enum):
    UNSET = "unset"; OK = "ok"; ERROR = "error"

@dataclass
class Span:
    span_id: str; trace_id: str; parent_span_id: Optional[str]; name: str; kind: SpanKind
    start_time_ns: int; end_time_ns: Optional[int]; attributes: Dict[str, Any]
    events: List[Dict]; status: SpanStatus; status_message: Optional[str]

@dataclass
class Trace:
    trace_id: str; spans: List[Span]; start_time_ns: int; end_time_ns: int; service_name: str

@dataclass
class SamplingConfig:
    strategy: str; param: float; target_service: Optional[str] = None

class SpanStore:
    def __init__(self, max_spans: int = 100000):
        self.spans: Dict[str, List[Span]] = {}
        self._lock = threading.Lock()
        self.max_spans = max_spans
        self._total = 0
    def add_span(self, span: Span):
        with self._lock:
            if span.trace_id not in self.spans:
                self.spans[span.trace_id] = []
            self.spans[span.trace_id].append(span)
            self._total += 1
            while self._total > self.max_spans:
                oldest_tid = next(iter(self.spans))
                self._total -= len(self.spans[oldest_tid])
                del self.spans[oldest_tid]
    def get_trace(self, trace_id: str) -> Optional[Trace]:
        with self._lock:
            spans = self.spans.get(trace_id)
            if not spans: return None
            start = min(s.start_time_ns for s in spans)
            end = max(s.end_time_ns or start for s in spans)
            return Trace(trace_id=trace_id, spans=spans, start_time_ns=start, end_time_ns=end, service_name="crownstar")
    def query_spans(self, service: str = None, operation: str = None, start_time: int = None, end_time: int = None, limit: int = 100) -> List[Span]:
        results = []
        with self._lock:
            for tid, spans in self.spans.items():
                for span in spans:
                    if service and span.attributes.get("service") != service: continue
                    if operation and span.name != operation: continue
                    if start_time and span.start_time_ns < start_time: continue
                    if end_time and (span.end_time_ns or span.start_time_ns) > end_time: continue
                    results.append(span)
                    if len(results) >= limit: break
                if len(results) >= limit: break
        return results

class Tracer:
    _current_span: ContextVar[Optional[Span]] = ContextVar("current_span", default=None)
    def __init__(self, service_name: str, store: SpanStore, sampler: "Sampler"):
        self.service_name = service_name; self.store = store; self.sampler = sampler
    def start_span(self, name: str, kind: SpanKind = SpanKind.INTERNAL, attributes: Dict = None, parent_span: Optional[Span] = None):
        parent = parent_span or Tracer._current_span.get()
        trace_id = parent.trace_id if parent else self._new_trace_id()
        span_id = self._new_span_id()
        parent_span_id = parent.span_id if parent else None
        if not parent and not self.sampler.should_sample(trace_id):
            return SpanContext(span_id, trace_id, parent_span_id, name, sampled=False, tracer=self)
        span = Span(span_id=span_id, trace_id=trace_id, parent_span_id=parent_span_id, name=name, kind=kind, start_time_ns=time.time_ns(), end_time_ns=None, attributes=attributes or {}, events=[], status=SpanStatus.UNSET, status_message=None)
        span.attributes["service"] = self.service_name
        ctx = SpanContext(span.span_id, span.trace_id, parent_span_id, name, sampled=True, tracer=self)
        ctx._span = span
        self._activate(ctx)
        return ctx
    def _new_trace_id(self): return uuid.uuid4().hex[:32]
    def _new_span_id(self): return uuid.uuid4().hex[:16]
    def _activate(self, ctx): self._current_span.set(ctx._span); ctx._active = True
    def _deactivate(self): self._current_span.set(None)

class SpanContext:
    def __init__(self, span_id: str, trace_id: str, parent_span_id: Optional[str], name: str, sampled: bool, tracer: Tracer):
        self.span_id = span_id; self.trace_id = trace_id; self.parent_span_id = parent_span_id
        self.name = name; self.sampled = sampled; self._tracer = tracer
        self._span: Optional[Span] = None; self._active = False
    def __enter__(self):
        if self.sampled and self._span: self._tracer._activate(self)
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.sampled and self._span:
            self._span.end_time_ns = time.time_ns()
            if exc_val: self._span.status = SpanStatus.ERROR; self._span.status_message = str(exc_val)
            else:
                if self._span.status == SpanStatus.UNSET: self._span.status = SpanStatus.OK
            self._tracer.store.add_span(self._span)
            self._tracer._deactivate()
    def set_attribute(self, key: str, value: Any): 
        if self._span: self._span.attributes[key] = value
    def add_event(self, name: str, attributes: Dict = None):
        if self._span: self._span.events.append({"timestamp": time.time_ns(), "name": name, "attributes": attributes or {}})
    def set_status(self, status: SpanStatus, message: str = None):
        if self._span: self._span.status = status; self._span.status_message = message

class Sampler:
    def __init__(self, config: SamplingConfig): self.config = config
    def should_sample(self, trace_id: str) -> bool:
        if self.config.strategy == "always_on": return True
        if self.config.strategy == "always_off": return False
        if self.config.strategy == "probabilistic":
            r = int(trace_id[:8], 16) / 0xffffffff
            return r < self.config.param
        return True

class JaegerExporter:
    def __init__(self, config: Dict):
        self.enabled = config.get("enabled", False)
        self.agent_host = config.get("agent_host", "localhost")
        self.agent_port = config.get("agent_port", 6831)
        self._client = None
        if self.enabled:
            try:
                from jaeger_client import Config
                cfg = Config(config={"sampler": {"type": "const", "param": 1}, "local_agent": {"reporting_host": self.agent_host, "reporting_port": self.agent_port}, "logging": False}, service_name="crownstar")
                self._client = cfg.initialize_tracer()
            except ImportError:
                logger.warning("jaeger-client not installed; Jaeger export disabled")
                self.enabled = False
    def export_span(self, span: Span):
        if not self.enabled or not self._client: return
        # stub for Jaeger export

class ObservabilityManager:
    def __init__(self, config_path="config/tracing/config.json"):
        self.config = self._load_config(config_path)
        self.store = SpanStore(max_spans=self.config.get("max_spans", 100000))
        sampler_config = SamplingConfig(**self.config["sampling"])
        self.sampler = Sampler(sampler_config)
        self.tracer = Tracer("crownstar", self.store, self.sampler)
        self.jaeger = JaegerExporter(self.config.get("jaeger", {}))
        self._start_background_export()
    def _load_config(self, path):
        default = {"sampling": {"strategy": "probabilistic", "param": 0.1}, "max_spans": 100000, "jaeger": {"enabled": False, "agent_host": "localhost", "agent_port": 6831}}
        if os.path.exists(path):
            with open(path, 'r') as f: default.update(json.load(f))
        return default
    def _start_background_export(self):
        def export_loop():
            while True: time.sleep(5)
        threading.Thread(target=export_loop, daemon=True).start()
    def get_trace(self, trace_id: str) -> Optional[Trace]: return self.store.get_trace(trace_id)
    def query_spans(self, **kwargs) -> List[Span]: return self.store.query_spans(**kwargs)
    def get_stats(self) -> Dict:
        total_spans = sum(len(spans) for spans in self.store.spans.values())
        return {"total_traces": len(self.store.spans), "total_spans": total_spans, "sampling_strategy": self.config["sampling"]["strategy"], "sampling_param": self.config["sampling"]["param"], "jaeger_enabled": self.jaeger.enabled}
    def update_sampling(self, strategy: str, param: float):
        self.config["sampling"] = {"strategy": strategy, "param": param}
        self.sampler = Sampler(SamplingConfig(strategy, param))
        with open("config/tracing/config.json", 'w') as f: json.dump(self.config, f, indent=2)

_obs_manager = None
def get_obs_manager():
    global _obs_manager
    if _obs_manager is None: _obs_manager = ObservabilityManager()
    return _obs_manager
