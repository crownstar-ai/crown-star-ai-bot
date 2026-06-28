# monitoring/tracing.py – OpenTelemetry distributed tracing
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
import os

def setup_tracing(app, service_name="crownstar-api"):
    """Configure OpenTelemetry tracing with Jaeger exporter"""
    if not os.environ.get("OTEL_ENABLED", "false").lower() == "true":
        return
    
    resource = Resource(attributes={SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)
    
    jaeger_exporter = JaegerExporter(
        agent_host_name=os.environ.get("JAEGER_HOST", "localhost"),
        agent_port=int(os.environ.get("JAEGER_PORT", 6831)),
    )
    
    provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))
    trace.set_tracer_provider(provider)
    
    # Instrument FastAPI
    FastAPIInstrumentor.instrument_app(app)
    
    # Instrument requests library
    RequestsInstrumentor().instrument()
    
    print("✅ OpenTelemetry tracing enabled (Jaeger)")

def get_tracer():
    return trace.get_tracer(__name__)

def trace_request(func):
    """Decorator to trace async functions"""
    async def wrapper(*args, **kwargs):
        tracer = get_tracer()
        with tracer.start_as_current_span(func.__name__):
            return await func(*args, **kwargs)
    return wrapper
