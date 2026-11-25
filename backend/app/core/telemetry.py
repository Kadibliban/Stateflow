"""
StateFlow OpenTelemetry Configuration

Distributed tracing setup with OpenTelemetry for FastAPI, SQLAlchemy, Redis, and Celery.
"""
import os
from typing import Optional

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.semconv.resource import ResourceAttributes

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Global tracer and meter providers
_tracer_provider: Optional[TracerProvider] = None
_meter_provider: Optional[MeterProvider] = None


def init_telemetry(app_name: str = None, environment: str = None) -> None:
    """Initialize OpenTelemetry tracing and metrics."""
    global _tracer_provider, _meter_provider

    service_name = app_name or settings.APP_NAME
    env = environment or settings.ENVIRONMENT

    # Create resource with service information
    resource = Resource.create({
        ResourceAttributes.SERVICE_NAME: service_name,
        ResourceAttributes.SERVICE_VERSION: settings.APP_VERSION,
        ResourceAttributes.DEPLOYMENT_ENVIRONMENT: env,
        "service.instance.id": os.getenv("HOSTNAME", "unknown"),
    })

    # Initialize Tracer Provider
    _tracer_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(_tracer_provider)

    # Configure span exporters
    if settings.OTLP_ENDPOINT:
        otlp_exporter = OTLPSpanExporter(
            endpoint=settings.OTLP_ENDPOINT,
            insecure=settings.OTLP_INSECURE,
        )
        _tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        logger.info("OTLP trace exporter configured", endpoint=settings.OTLP_ENDPOINT)

    # Add console exporter for development
    if env == "development":
        _tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        logger.info("Console span exporter enabled for development")

    # Initialize Meter Provider with Prometheus exporter
    prometheus_reader = PrometheusMetricReader()
    _meter_provider = MeterProvider(resource=resource, metric_readers=[prometheus_reader])

    logger.info("OpenTelemetry initialized", service=service_name, environment=env)


def instrument_fastapi(app) -> None:
    """Instrument FastAPI application with OpenTelemetry."""
    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=_tracer_provider,
        excluded_urls="/health,/health/ready,/health/live,/metrics",
    )
    logger.info("FastAPI instrumentation enabled")


def instrument_sqlalchemy(engine) -> None:
    """Instrument SQLAlchemy engine with OpenTelemetry.

    For async engines, we need to instrument the sync_engine as
    SQLAlchemy's async engine doesn't support async event listeners.
    """
    # Use sync_engine for async engines
    sync_engine = getattr(engine, 'sync_engine', engine)

    SQLAlchemyInstrumentor().instrument(
        engine=sync_engine,
        tracer_provider=_tracer_provider,
    )
    logger.info("SQLAlchemy instrumentation enabled")


def instrument_redis() -> None:
    """Instrument Redis client with OpenTelemetry."""
    RedisInstrumentor().instrument(
        tracer_provider=_tracer_provider,
    )
    logger.info("Redis instrumentation enabled")


def instrument_celery(celery_app) -> None:
    """Instrument Celery app with OpenTelemetry."""
    CeleryInstrumentor().instrument(
        celery_app=celery_app,
        tracer_provider=_tracer_provider,
    )
    logger.info("Celery instrumentation enabled")


def get_tracer(name: str):
    """Get a tracer instance."""
    return trace.get_tracer_provider().get_tracer(name)


def get_meter(name: str):
    """Get a meter instance."""
    return _meter_provider.get_meter(name) if _meter_provider else None


def shutdown_telemetry() -> None:
    """Shutdown OpenTelemetry providers."""
    global _tracer_provider, _meter_provider

    if _tracer_provider:
        _tracer_provider.shutdown()
        _tracer_provider = None

    if _meter_provider:
        _meter_provider.shutdown()
        _meter_provider = None

    logger.info("OpenTelemetry shutdown complete")