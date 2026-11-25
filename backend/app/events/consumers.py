"""
StateFlow Event Consumers

RabbitMQ consumers for handling workflow execution events.
"""
import asyncio
import json
from typing import Any, Callable, Dict, Optional, Set
from uuid import UUID

import aio_pika
from aio_pika import ExchangeType, IncomingMessage

from app.core.config import settings
from app.core.database import get_session_context, close_db
from app.core.logging import get_logger
from app.models.event import OutboxEvent
from app.models.idempotency import IdempotencyRecord
from app.repositories.event_repository import OutboxRepository
from app.repositories.execution_repository import IdempotencyRepository

logger = get_logger(__name__)


class EventConsumer:
    """Base class for RabbitMQ event consumers."""

    def __init__(
        self,
        queue_name: str,
        exchange_name: str,
        routing_keys: list[str],
        handler: Callable,
        prefetch_count: int = 10,
    ):
        self.queue_name = queue_name
        self.exchange_name = exchange_name
        self.routing_keys = routing_keys
        self.handler = handler
        self.prefetch_count = prefetch_count
        self._connection: Optional[aio_pika.Connection] = None
        self._channel: Optional[aio_pika.Channel] = None
        self._queue: Optional[aio_pika.Queue] = None
        self._running = False

    async def connect(self) -> None:
        """Establish connection to RabbitMQ."""
        if self._connection and not self._connection.is_closed:
            return

        self._connection = await aio_pika.connect_robust(
            settings.RABBITMQ_URL,
            client_properties={"connection_name": f"stateflow-consumer-{self.queue_name}"},
        )
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=self.prefetch_count)

        # Declare exchange
        exchange = await self._channel.declare_exchange(
            self.exchange_name,
            ExchangeType.TOPIC,
            durable=True,
        )

        # Declare queue
        self._queue = await self._channel.declare_queue(
            self.queue_name,
            durable=True,
        )

        # Bind queue to exchange with routing keys
        for routing_key in self.routing_keys:
            await self._queue.bind(exchange, routing_key=routing_key)

        logger.info(
            "Event consumer connected",
            queue=self.queue_name,
            exchange=self.exchange_name,
            routing_keys=self.routing_keys,
        )

    async def disconnect(self) -> None:
        """Close connection to RabbitMQ."""
        self._running = False
        if self._queue and not self._queue.channel.is_closed:
            await self._queue.cancel()
        if self._channel and not self._channel.is_closed:
            await self._channel.close()
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
        logger.info("Event consumer disconnected", queue=self.queue_name)

    async def start_consuming(self) -> None:
        """Start consuming messages."""
        if not self._queue:
            await self.connect()

        self._running = True

        async def process_message(message: IncomingMessage) -> None:
            async with message.process():
                await self._handle_message(message)

        await self._queue.consume(process_message)
        logger.info("Started consuming messages", queue=self.queue_name)

        # Keep the consumer running
        while self._running:
            await asyncio.sleep(1)

    async def _handle_message(self, message: IncomingMessage) -> None:
        """Handle incoming message with idempotency and error handling."""
        message_id = message.message_id or "unknown"
        correlation_id = message.correlation_id

        logger.debug(
            "Received message",
            queue=self.queue_name,
            message_id=message_id,
            correlation_id=correlation_id,
        )

        try:
            # Parse message body
            payload = json.loads(message.body.decode())

            # Check idempotency for message processing
            idempotency_key = f"consumer:{self.queue_name}:{message_id}"
            if await self._check_and_lock_idempotency(idempotency_key):
                # Message already processed
                logger.debug("Message already processed (idempotent)", message_id=message_id)
                return

            # Process message
            await self.handler(payload, message.headers or {})

            # Mark as completed
            await self._complete_idempotency(idempotency_key)

            logger.debug("Message processed successfully", message_id=message_id)

        except json.JSONDecodeError as e:
            logger.error("Failed to decode message", message_id=message_id, error=str(e))
            # Don't requeue - message is malformed
        except Exception as e:
            logger.error(
                "Error processing message",
                message_id=message_id,
                correlation_id=correlation_id,
                error=str(e),
            )
            # Requeue for retry (will be handled by RabbitMQ's requeue on exception)
            raise

    async def _check_and_lock_idempotency(self, idempotency_key: str) -> bool:
        """Check if message was already processed. Returns True if already processed."""
        async with get_session_context() as session:
            repo = IdempotencyRepository(session)
            existing = await repo.get_valid_by_key("consumer", idempotency_key)
            if existing and existing.completed:
                return True

            # Create or lock idempotency record
            if existing:
                # Try to lock
                locked = await repo.lock(existing.id, lock_ttl_seconds=300)
                return not locked
            else:
                # Create new record
                from datetime import datetime, timezone, timedelta
                record = IdempotencyRecord(
                    idempotency_key=idempotency_key,
                    organization_id=UUID("00000000-0000-0000-0000-000000000000"),  # Will be overridden
                    scope="consumer",
                    request_hash="",
                    response_data={},
                    completed=False,
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
                )
                await repo.create(record)
                return False

    async def _complete_idempotency(self, idempotency_key: str) -> None:
        """Mark idempotency record as completed."""
        async with get_session_context() as session:
            repo = IdempotencyRepository(session)
            existing = await repo.get_valid_by_key("consumer", idempotency_key)
            if existing:
                await repo.complete(existing.id, {"status": "completed"})


class WorkflowExecutionEventConsumer(EventConsumer):
    """Consumer for workflow execution events."""

    def __init__(self, handler: Callable):
        super().__init__(
            queue_name="workflow_execution_events",
            exchange_name="stateflow.workflow_execution",
            routing_keys=["workflow_execution.*"],
            handler=handler,
        )


class StepExecutionEventConsumer(EventConsumer):
    """Consumer for step execution events."""

    def __init__(self, handler: Callable):
        super().__init__(
            queue_name="step_execution_events",
            exchange_name="stateflow.step_execution",
            routing_keys=["step_execution.*"],
            handler=handler,
        )


class CompensationEventConsumer(EventConsumer):
    """Consumer for compensation events."""

    def __init__(self, handler: Callable):
        super().__init__(
            queue_name="compensation_events",
            exchange_name="stateflow.compensation_execution",
            routing_keys=["compensation_execution.*"],
            handler=handler,
        )


# Handler functions
async def handle_workflow_execution_event(payload: Dict[str, Any], headers: Dict[str, str]) -> None:
    """Handle workflow execution events."""
    event_type = payload.get("event_type", "unknown")
    execution_id = payload.get("execution_id")
    workflow_id = payload.get("workflow_id")

    logger.info(
        "Processing workflow execution event",
        event_type=event_type,
        execution_id=execution_id,
        workflow_id=workflow_id,
    )

    # Here you could:
    # - Send notifications
    # - Update external systems
    # - Trigger downstream workflows
    # - Update analytics/metrics

    # For now, just log
    pass


async def handle_step_execution_event(payload: Dict[str, Any], headers: Dict[str, str]) -> None:
    """Handle step execution events."""
    event_type = payload.get("event_type", "unknown")
    execution_id = payload.get("execution_id")
    step_execution_id = payload.get("step_execution_id")
    step_key = payload.get("event_data", {}).get("step_key", "unknown")

    logger.info(
        "Processing step execution event",
        event_type=event_type,
        execution_id=execution_id,
        step_execution_id=step_execution_id,
        step_key=step_key,
    )

    # Here you could:
    # - Track step-level metrics
    # - Send real-time updates to frontend
    # - Trigger dependent actions

    pass


async def handle_compensation_event(payload: Dict[str, Any], headers: Dict[str, str]) -> None:
    """Handle compensation events."""
    event_type = payload.get("event_type", "unknown")
    execution_id = payload.get("execution_id")
    compensation_execution_id = payload.get("compensation_execution_id")
    step_key = payload.get("event_data", {}).get("step_key", "unknown")

    logger.info(
        "Processing compensation event",
        event_type=event_type,
        execution_id=execution_id,
        compensation_execution_id=compensation_execution_id,
        step_key=step_key,
    )

    # Here you could:
    # - Alert on compensation failures
    # - Trigger manual intervention workflows
    # - Update compensation tracking

    pass


# Consumer runner
async def run_consumers() -> None:
    """Run all event consumers."""
    consumers = [
        WorkflowExecutionEventConsumer(handle_workflow_execution_event),
        StepExecutionEventConsumer(handle_step_execution_event),
        CompensationEventConsumer(handle_compensation_event),
    ]

    for consumer in consumers:
        await consumer.connect()

    # Start all consumers concurrently
    await asyncio.gather(*[consumer.start_consuming() for consumer in consumers])