"""
StateFlow Consumer Tasks

Celery tasks for running event consumers.
"""
import asyncio
from typing import Any, Dict

from celery import shared_task

from app.core.database import get_session_context, close_db
from app.core.logging import get_logger
from app.events.consumers import run_consumers

logger = get_logger(__name__)


def _run_async(coro):
    """Run an async coroutine in a new event loop, ensuring proper cleanup."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        # Close the database connections before closing the loop
        try:
            loop.run_until_complete(close_db())
        except Exception:
            pass
        loop.close()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def run_event_consumers(self) -> Dict[str, Any]:
    """Run event consumers (typically run as a long-running worker)."""
    try:
        # This task runs the consumers - in production, you'd run this as a dedicated worker
        # For Celery beat, we just check if consumers should be running
        result = _run_async(run_consumers())
        return {"status": "success", "result": result}
    except Exception as exc:
        logger.error("Event consumers failed", error=str(exc))
        raise self.retry(exc=exc)


@shared_task
def check_consumer_health() -> Dict[str, Any]:
    """Check health of consumer connections."""
    from app.core.config import settings
    import aio_pika

    async def _check():
        try:
            connection = await aio_pika.connect_robust(
                settings.RABBITMQ_URL,
                client_properties={"connection_name": "stateflow-health-check"},
            )
            await connection.close()
            return {"status": "healthy", "rabbitmq": "connected"}
        except Exception as e:
            return {"status": "unhealthy", "rabbitmq": "disconnected", "error": str(e)}

    try:
        result = _run_async(_check())
        return {"status": "success", "result": result}
    except Exception as exc:
        logger.error("Consumer health check failed", error=str(exc))
        return {"status": "error", "error": str(exc)}