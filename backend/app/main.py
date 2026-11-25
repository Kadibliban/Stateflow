"""
StateFlow Main Application

FastAPI application entry point with all routes, middleware, and lifecycle management.
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest
from prometheus_client.openmetrics.exposition import CONTENT_TYPE_LATEST

from app.core.config import settings
from app.core.database import close_db, init_db
from app.core.logging import get_logger, setup_logging
from app.core.telemetry import (
    get_tracer,
    init_telemetry,
    instrument_fastapi,
    instrument_sqlalchemy,
    instrument_redis,
    instrument_celery,
    shutdown_telemetry,
)
from app.api.v1.api import api_router

logger = get_logger(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    # Startup
    logger.info("Starting StateFlow application", version=settings.APP_VERSION)
    setup_logging()

    # Initialize OpenTelemetry
    if settings.TRACING_ENABLED:
        init_telemetry()
        logger.info("OpenTelemetry initialized")

    await init_db()
    logger.info("Database initialized")

    # Instrument Redis after database is initialized
    # Note: SQLAlchemy is already instrumented in database.py create_engine()
    if settings.TRACING_ENABLED:
        instrument_redis()

    yield

    # Shutdown
    logger.info("Shutting down StateFlow application")
    if settings.TRACING_ENABLED:
        shutdown_telemetry()
    await close_db()
    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Distributed Transaction and Process Management Platform",
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
        openapi_url="/openapi.json" if settings.ENVIRONMENT != "production" else None,
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.CORS_ALLOW_METHODS,
        allow_headers=settings.CORS_ALLOW_HEADERS,
    )

    # Instrument FastAPI with OpenTelemetry
    if settings.TRACING_ENABLED:
        instrument_fastapi(app)

    # Request logging and metrics middleware
    @app.middleware("http")
    async def logging_metrics_middleware(request: Request, call_next):
        import time
        start_time = time.time()

        # Generate correlation ID
        correlation_id = request.headers.get("X-Correlation-ID", "")
        if not correlation_id:
            import uuid
            correlation_id = str(uuid.uuid4())

        # Process request
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            status_code = 500
            logger.error(
                "Request failed",
                method=request.method,
                path=request.url.path,
                error=str(e),
                correlation_id=correlation_id,
            )
            raise

        # Record metrics
        duration = time.time() - start_time
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status=status_code,
        ).inc()
        REQUEST_LATENCY.labels(
            method=request.method,
            endpoint=request.url.path,
        ).observe(duration)

        # Add correlation ID to response
        response.headers["X-Correlation-ID"] = correlation_id

        # Log request
        logger.info(
            "HTTP request",
            method=request.method,
            path=request.url.path,
            status=status_code,
            duration_ms=round(duration * 1000, 2),
            correlation_id=correlation_id,
        )

        return response

    # Include API router
    app.include_router(api_router, prefix="/api/v1")

    # Health check endpoints (outside API versioning)
    @app.get("/health", tags=["Health"])
    async def health_check() -> dict:
        """Basic health check endpoint."""
        from app.core.database import check_db_connection

        db_healthy = await check_db_connection()

        return {
            "status": "healthy" if db_healthy else "unhealthy",
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "database": "connected" if db_healthy else "disconnected",
        }

    @app.get("/health/ready", tags=["Health"])
    async def readiness_check() -> dict:
        """Readiness check for Kubernetes."""
        from app.core.database import check_db_connection

        db_healthy = await check_db_connection()

        if not db_healthy:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "database": "disconnected",
                },
            )

        return {
            "status": "ready",
            "database": "connected",
        }

    @app.get("/health/live", tags=["Health"])
    async def liveness_check() -> dict:
        """Liveness check for Kubernetes."""
        return {"status": "alive"}

    @app.get("/metrics", tags=["Monitoring"])
    async def metrics() -> Response:
        """Prometheus metrics endpoint."""
        # generate_latest() in prometheus-client 0.19.0 doesn't include # EOF marker
        # Add it manually to satisfy Prometheus scraper
        content = generate_latest() + b"# EOF\n"
        return Response(
            content=content,
            media_type=CONTENT_TYPE_LATEST,
        )

    # Root endpoint
    @app.get("/", tags=["Root"])
    async def root() -> dict:
        """Root endpoint with API information."""
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "description": "Distributed Transaction and Process Management Platform",
            "docs": "/docs",
            "health": "/health",
        }

    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.ENVIRONMENT == "development",
        log_level=settings.LOG_LEVEL.lower(),
    )