"""
StateFlow Event Service

Business logic for event publishing and outbox management.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import OutboxEvent
from app.repositories.event_repository import OutboxRepository
from app.repositories.execution_repository import ExecutionRepository
from app.models.execution import WorkflowExecution


class EventService:
    """Service for event operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.outbox_repo = OutboxRepository(session)
        self.execution_repo = ExecutionRepository(session)

    async def publish_event(
        self,
        aggregate_type: str,
        aggregate_id: str,
        event_type: str,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
        max_retries: int = 5,
    ) -> OutboxEvent:
        """Create an outbox event for reliable publishing."""
        event = OutboxEvent(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            payload=payload,
            headers=headers or {},
            max_retries=max_retries,
        )
        return await self.outbox_repo.create(event)

    async def publish_batch(
        self,
        events: List[Dict[str, Any]],
    ) -> List[OutboxEvent]:
        """Create multiple outbox events."""
        outbox_events = [
            OutboxEvent(
                aggregate_type=e["aggregate_type"],
                aggregate_id=e["aggregate_id"],
                event_type=e["event_type"],
                payload=e["payload"],
                headers=e.get("headers", {}),
                max_retries=e.get("max_retries", 5),
            )
            for e in events
        ]
        return await self.outbox_repo.create_batch(outbox_events)

    async def get_pending_events(self, limit: int = 100) -> List[OutboxEvent]:
        """Get unpublished events ready for publishing."""
        return await self.outbox_repo.get_unpublished(limit=limit)

    async def mark_published(self, event_ids: List[UUID]) -> int:
        """Mark events as published."""
        return await self.outbox_repo.mark_published(event_ids)

    async def handle_publish_failure(
        self, event_id: UUID, error: str, retry_delay_seconds: float = 5.0
    ) -> bool:
        """Handle publish failure with exponential backoff."""
        from datetime import timedelta
        next_retry = datetime.now(timezone.utc) + timedelta(seconds=retry_delay_seconds)
        return await self.outbox_repo.increment_retry(event_id, error, next_retry)

    async def get_events_for_aggregate(
        self, aggregate_type: str, aggregate_id: str
    ) -> List[OutboxEvent]:
        """Get all outbox events for an aggregate."""
        return await self.outbox_repo.get_by_aggregate(aggregate_type, aggregate_id)

    async def cleanup_old_events(self, days: int = 30) -> int:
        """Clean up old published events."""
        return await self.outbox_repo.cleanup_old_published(days=days)

    async def log_execution_event(
        self,
        execution_id: UUID,
        event_type: str,
        event_data: Dict[str, Any],
        message: Optional[str] = None,
        step_execution_id: Optional[UUID] = None,
        compensation_execution_id: Optional[UUID] = None,
    ) -> OutboxEvent:
        """Log an execution event to outbox."""
        execution = await self.execution_repo.get_by_id(execution_id)
        if not execution:
            raise ValueError("Execution not found")

        return await self.publish_event(
            aggregate_type="workflow_execution",
            aggregate_id=str(execution_id),
            event_type=event_type,
            payload={
                "execution_id": str(execution_id),
                "workflow_id": str(execution.workflow_id),
                "organization_id": str(execution.organization_id),
                "event_data": event_data,
                "message": message,
                "step_execution_id": str(step_execution_id) if step_execution_id else None,
                "compensation_execution_id": str(compensation_execution_id) if compensation_execution_id else None,
            },
            headers={
                "correlation_id": execution.correlation_id or "",
            },
        )