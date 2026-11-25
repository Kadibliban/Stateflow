"""
StateFlow Celery Tasks

Background task definitions for workflow execution.
"""
import os
from celery import Celery
from celery.signals import worker_init, worker_shutdown, worker_process_init
from kombu import Queue

from app.core.config import settings

# Create Celery app
celery_app = Celery("stateflow")

# Configure Celery
celery_app.conf.update(
    broker_url=settings.CELERY_BROKER_URL,
    result_backend=settings.CELERY_RESULT_BACKEND,
    task_serializer=settings.CELERY_TASK_SERIALIZER,
    result_serializer=settings.CELERY_RESULT_SERIALIZER,
    accept_content=settings.CELERY_ACCEPT_CONTENT,
    timezone=settings.CELERY_TIMEZONE,
    enable_utc=True,
    task_track_started=settings.CELERY_TASK_TRACK_STARTED,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    worker_prefetch_multiplier=settings.CELERY_WORKER_PREFETCH_MULTIPLIER,
    worker_max_tasks_per_child=100,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Task routing
    task_routes={
        "app.workers.execution_tasks.execute_workflow": {"queue": "workflow_execution"},
        "app.workers.execution_tasks.execute_step": {"queue": "step_execution"},
        "app.workers.execution_tasks.execute_compensation": {"queue": "compensation"},
        "app.workers.execution_tasks.execute_saga_compensation": {"queue": "scheduler"},
        "app.workers.outbox_tasks.publish_outbox_events": {"queue": "outbox"},
        "app.workers.scheduler_tasks.retry_scheduler": {"queue": "scheduler"},
        "app.workers.consumer_tasks.check_consumer_health": {"queue": "scheduler"},
    },
    # Queue definitions
    task_queues=(
        Queue("workflow_execution", routing_key="workflow_execution"),
        Queue("step_execution", routing_key="step_execution"),
        Queue("compensation", routing_key="compensation"),
        Queue("outbox", routing_key="outbox"),
        Queue("scheduler", routing_key="scheduler"),
        Queue("consumer", routing_key="consumer"),
        Queue("default", routing_key="default"),
    ),
    # Beat schedule
    beat_schedule={
        "retry-scheduler": {
            "task": "app.workers.scheduler_tasks.retry_scheduler",
            "schedule": 10.0,  # Every 10 seconds
        },
        "outbox-publisher": {
            "task": "app.workers.outbox_tasks.publish_outbox_events",
            "schedule": 5.0,  # Every 5 seconds
        },
        "cleanup-expired": {
            "task": "app.workers.scheduler_tasks.cleanup_expired",
            "schedule": 3600.0,  # Every hour
        },
        "check-stale-executions": {
            "task": "app.workers.scheduler_tasks.check_stale_executions",
            "schedule": 60.0,  # Every minute
        },
        "recover-step-executions": {
            "task": "app.workers.scheduler_tasks.recover_step_executions",
            "schedule": 30.0,  # Every 30 seconds
        },
        "recover-compensation-executions": {
            "task": "app.workers.scheduler_tasks.recover_compensation_executions",
            "schedule": 30.0,  # Every 30 seconds
        },
        "check-consumer-health": {
            "task": "app.workers.consumer_tasks.check_consumer_health",
            "schedule": 60.0,  # Every minute
        },
    },
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["app.workers"])


@worker_process_init.connect
def init_worker(**kwargs):
    """Initialize worker on startup (runs in each child process after fork).

    We only reset the engine/session factory globals here. The actual engine
    creation is deferred to the first task execution, which runs in the
    task's event loop. This avoids event loop mismatch issues with asyncpg.
    """
    import os
    from app.core.logging import setup_logging, get_logger

    setup_logging()
    logger = get_logger("worker")

    # Reset engine in worker process (asyncpg connections don't survive fork)
    # The engine will be lazily created in the task's event loop
    import app.core.database as db_module
    db_module._engine = None
    db_module._session_factory = None

    logger.info("worker_process_init firing, engine reset", pid=os.getpid())


@worker_init.connect
def init_celery_telemetry(**kwargs):
    """Initialize OpenTelemetry for Celery worker."""
    from app.core.config import settings
    from app.core.telemetry import init_telemetry, instrument_celery, instrument_sqlalchemy, instrument_redis

    if settings.TRACING_ENABLED:
        init_telemetry()
        # Instrument Celery
        instrument_celery(celery_app)
        # Instrument Redis
        instrument_redis()
        # Note: SQLAlchemy will be instrumented when engine is created in task
        logger = get_logger("worker")
        logger.info("Celery OpenTelemetry instrumentation enabled")


@worker_shutdown.connect
def shutdown_worker(**kwargs):
    """Cleanup on worker shutdown."""
    import asyncio
    from app.core.database import close_db
    from app.core.logging import get_logger

    logger = get_logger("worker")
    try:
        asyncio.run(close_db())
        logger.info("Worker database connections closed")
    except Exception as e:
        logger.error("Failed to close worker database", error=str(e))


# Import task modules to register them
from app.workers import execution_tasks  # noqa: E402
from app.workers import outbox_tasks  # noqa: E402
from app.workers import scheduler_tasks  # noqa: E402
from app.workers import consumer_tasks  # noqa: E402