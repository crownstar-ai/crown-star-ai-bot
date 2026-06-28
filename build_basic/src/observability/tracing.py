# observability/tracing.py – OpenTelemetry tracing with Jaeger
import os
import time
from functools import wraps
from typing import Optional, Dict, Any
from contextvars import ContextVar

# Lazy imports to avoid heavy deps if not installed
_otel_available = False
_tracer_provider = None
_tracer = None
_current_span = ContextVar("current_span", default=None)

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.exporter.jaeger.thrift import JaegerExporter
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
    from opentelemetry.propagate import set_global_textmap
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    _otel_available = True
except ImportError:
    print("OpenTelemetry not installed. Install with: pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-jaeger opentelemetry-instrumentation-fastapi opentelemetry-instrumentation-requests")

def setup_tracing(service_name: str = "crownstar-api", jaeger_host: str = "localhost", jaeger_port: int = 6831, sample_rate: float = 1.0):
    """Configure OpenTelemetry with Jaeger exporter"""
    if not _otel_available:
        print("OpenTelemetry unavailable – tracing disabled")
        return None
    
    resource = Resource(attributes={
        SERVICE_NAME: service_name,
        "service.version": "7.0.1",
        "deployment.environment": os.environ.get("ENVIRONMENT", "development")
    })
    
    provider = TracerProvider(resource=resource)
    
    # Jaeger exporter
    jaeger_exporter = JaegerExporter(
        agent_host_name=jaeger_host,
        agent_port=jaeger_port,
    )
    provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))
    
    # Also export to console for debugging (optional)
    if os.environ.get("OTEL_CONSOLE_EXPORTER", "false").lower() == "true":
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    
    trace.set_tracer_provider(provider)
    
    # Set global propagator for trace context
    set_global_textmap(TraceContextTextMapPropagator())
    
    global _tracer, _tracer_provider
    _tracer_provider = provider
    _tracer = trace.get_tracer(__name__)
    
    print(f"✅ OpenTelemetry tracing enabled (Jaeger: {jaeger_host}:{jaeger_port}, sample_rate={sample_rate})")
    return _tracer

def instrument_fastapi(app):
    """Auto-instrument FastAPI app"""
    if _otel_available:
        FastAPIInstrumentor.instrument_app(app)
        print("FastAPI instrumented for tracing")
        return True
    return False

def instrument_requests():
    """Auto-instrument requests library"""
    if _otel_available:
        RequestsInstrumentor().instrument()
        print("Requests library instrumented for tracing")

def get_tracer():
    """Return current tracer instance"""
    return _tracer

def trace_function(name: Optional[str] = None):
    """Decorator to trace a function"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not _tracer:
                return func(*args, **kwargs)
            span_name = name or func.__name__
            with _tracer.start_as_current_span(span_name):
                # Add function arguments as attributes (sanitized)
                span = trace.get_current_span()
                if span:
                    for i, arg in enumerate(args[:5]):  # limit to first 5 args
                        span.set_attribute(f"arg.{i}", str(arg)[:100])
                return func(*args, **kwargs)
        return wrapper
    return decorator

def get_current_trace_id() -> Optional[str]:
    """Get current trace ID from context"""
    if not _otel_available:
        return None
    span = trace.get_current_span()
    if span:
        ctx = span.get_span_context()
        if ctx.is_valid:
            return format(ctx.trace_id, '032x')
    return None

def add_span_event(name: str, attributes: Dict[str, Any] = None):
    """Add event to current span"""
    if _otel_available:
        span = trace.get_current_span()
        if span:
            span.add_event(name, attributes or {})
