"""
StateFlow Outbox Tasks

Celery tasks for publishing outbox events.
"""
import asyncio
import json
from typing import Any, Dict, List
from uuid import UUID

from celery import shared_task

from app.core.config import settings
from app.core.database import get_session_context, close_db
from app.core.logging import get_logger
from app.events.publisher import get_publisher, close_publisher
from app.models.event import OutboxEvent
from app.repositories.event_repository import OutboxRepository

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


@shared_task(bind=True, max_retries=5, default_retry_delay=30)
def publish_outbox_events(self) -> Dict[str, Any]:
    """Publish pending outbox events to RabbitMQ."""
    async def _publish():
        async with get_session_context() as session:
            outbox_repo = OutboxRepository(session)
            events = await outbox_repo.get_unpublished(
                limit=settings.OUTBOX_BATCH_SIZE,
                max_retries=settings.OUTBOX_MAX_RETRIES,
            )

            if not events:
                return {"published": 0, "failed": 0}

            publisher = await get_publisher()

            published_count = 0
            failed_count = 0

            for event in events:
                try:
                    # Determine exchange and routing key based on aggregate type
                    exchange_name = f"stateflow.{event.aggregate_type}"
                    routing_key = f"{event.aggregate_type}.{event.event_type}"

                    # Publish to RabbitMQ
                    await publisher.publish(
                        exchange_name=exchange_name,
                        routing_key=routing_key,
                        payload=event.payload,
                        headers=event.headers,
                        message_id=str(event.id),
                        correlation_id=event.headers.get("correlation_id"),
                    )

                    # Mark as published
                    await outbox_repo.mark_published([event.id])
                    published_count += 1

                    logger.debug(
                        "Published outbox event",
                        event_id=str(event.id),
                        exchange=exchange_name,
                        routing_key=routing_key,
                    )

                except Exception as e:
                    logger.error(
                        "Failed to publish outbox event",
                        event_id=str(event.id),
                        error=str(e),
                    )
                    # Schedule retry with exponential backoff
                    from datetime import datetime, timezone, timedelta
                    retry_delay = min(
                        2 ** event.retry_count * 5,  # 5s, 10s, 20s, 40s, 80s
                        300,  # Max 5 minutes
                    )
                    next_retry = datetime.now(timezone.utc) + timedelta(seconds=retry_delay)
                    await outbox_repo.increment_retry(event.id, str(e), next_retry)
                    failed_count += 1

            return {"published": published_count, "failed": failed_count}

    try:
        result = _run_async(_publish())
        return {"status": "success", "result": result}
    except Exception as exc:
        logger.error("Outbox publishing failed", error=str(exc))
        raise self.retry(exc=exc)


@shared_task
def retry_failed_outbox_events() -> Dict[str, Any]:
    """Retry failed outbox events that are ready for retry."""
    async def _retry():
        async with get_session_context() as session:
            outbox_repo = OutboxRepository(session)
            # Events with retry_count > 0 and next_retry_at <= now
            # are already picked up by get_unpublished
            # This task can be used for manual retry triggering
            return {"status": "completed"}

    try:
        result = _run_async(_retry())
        return {"status": "success", "result": result}
    except Exception as exc:
        logger.error("Outbox retry failed", error=str(exc))
        return {"status": "error", "error": str(exc)}