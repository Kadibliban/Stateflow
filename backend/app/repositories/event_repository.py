"""
StateFlow Event Repository

Data access layer for execution events and outbox events.
"""
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, update, delete, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import ExecutionEvent, OutboxEvent, EventType


class ExecutionEventRepository:
    """Repository for execution event operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, event: ExecutionEvent) -> ExecutionEvent:
        """Create a new execution event."""
        self.session.add(event)
        await self.session.flush()
        await self.session.refresh(event)
        return event

    async def create_batch(self, events: List[ExecutionEvent]) -> List[ExecutionEvent]:
        """Create multiple execution events."""
        self.session.add_all(events)
        await self.session.flush()
        for event in events:
            await self.session.refresh(event)
        return events

    async def get_by_id(self, event_id: UUID) -> Optional[ExecutionEvent]:
        """Get event by ID."""
        result = await self.session.execute(
            select(ExecutionEvent).where(ExecutionEvent.id == event_id)
        )
        return result.scalar_one_or_none()

    async def list_events(
        self,
        execution_id: UUID,
        event_type: Optional[EventType] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ExecutionEvent]:
        """List events for an execution."""
        query = select(ExecutionEvent).where(ExecutionEvent.execution_id == execution_id)

        if event_type:
            query = query.where(ExecutionEvent.event_type == event_type)

        query = query.order_by(ExecutionEvent.created_at).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def count_events(self, execution_id: UUID, event_type: Optional[EventType] = None) -> int:
        """Count events for an execution."""
        query = select(func.count(ExecutionEvent.id)).where(ExecutionEvent.execution_id == execution_id)
        if event_type:
            query = query.where(ExecutionEvent.event_type == event_type)
        result = await self.session.execute(query)
        return result.scalar() or 0

    async def get_event_summary(self, execution_id: UUID) -> List[dict]:
        """Get event count summary by type for an execution."""
        query = (
            select(ExecutionEvent.event_type, func.count(ExecutionEvent.id), func.max(ExecutionEvent.created_at))
            .where(ExecutionEvent.execution_id == execution_id)
            .group_by(ExecutionEvent.event_type)
        )
        result = await self.session.execute(query)
        return [
            {"event_type": row[0], "count": row[1], "last_occurrence": row[2]}
            for row in result.all()
        ]


class OutboxRepository:
    """Repository for outbox event operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, event: OutboxEvent) -> OutboxEvent:
        """Create a new outbox event."""
        self.session.add(event)
        await self.session.flush()
        await self.session.refresh(event)
        return event

    async def create_batch(self, events: List[OutboxEvent]) -> List[OutboxEvent]:
        """Create multiple outbox events."""
        self.session.add_all(events)
        await self.session.flush()
        for event in events:
            await self.session.refresh(event)
        return events

    async def get_unpublished(
        self, limit: int = 100, max_retries: int = 5
    ) -> List[OutboxEvent]:
        """Get unpublished events ready for publishing."""
        result = await self.session.execute(
            select(OutboxEvent)
            .where(
                OutboxEvent.published == False,
                OutboxEvent.retry_count < max_retries,
                (OutboxEvent.next_retry_at.is_(None)) | (OutboxEvent.next_retry_at <= datetime.now(timezone.utc)),
            )
            .order_by(OutboxEvent.created_at)
            .limit(limit)
        )
        return result.scalars().all()

    async def mark_published(self, event_ids: List[UUID]) -> int:
        """Mark events as published."""
        if not event_ids:
            return 0
        result = await self.session.execute(
            update(OutboxEvent)
            .where(OutboxEvent.id.in_(event_ids))
            .values(published=True, published_at=datetime.now(timezone.utc))
        )
        return result.rowcount

    async def increment_retry(self, event_id: UUID, error: str, next_retry_at: datetime) -> bool:
        """Increment retry count and update next retry time."""
        result = await self.session.execute(
            update(OutboxEvent)
            .where(OutboxEvent.id == event_id)
            .values(
                retry_count=OutboxEvent.retry_count + 1,
                last_error=error,
                next_retry_at=next_retry_at,
            )
        )
        return result.rowcount > 0

    async def get_by_aggregate(
        self, aggregate_type: str, aggregate_id: str
    ) -> List[OutboxEvent]:
        """Get outbox events by aggregate."""
        result = await self.session.execute(
            select(OutboxEvent)
            .where(
                OutboxEvent.aggregate_type == aggregate_type,
                OutboxEvent.aggregate_id == aggregate_id,
            )
            .order_by(OutboxEvent.created_at)
        )
        return result.scalars().all()

    async def cleanup_old_published(self, days: int = 30) -> int:
        """Clean up old published events."""
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = await self.session.execute(
            delete(OutboxEvent).where(
                OutboxEvent.published == True,
                OutboxEvent.published_at < cutoff,
            )
        )
        return result.rowcount


class EventRepository:
    """Combined repository for execution events and outbox events."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.execution_events = ExecutionEventRepository(session)
        self.outbox = OutboxRepository(session)

    async def create_event(self, event: ExecutionEvent) -> ExecutionEvent:
        """Create a new execution event."""
        return await self.execution_events.create(event)

    async def create_events_batch(self, events: List[ExecutionEvent]) -> List[ExecutionEvent]:
        """Create multiple execution events."""
        return await self.execution_events.create_batch(events)

    async def get_event(self, event_id: UUID) -> Optional[ExecutionEvent]:
        """Get event by ID."""
        return await self.execution_events.get_by_id(event_id)

    async def list_events(
        self,
        execution_id: UUID,
        event_type: Optional[EventType] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ExecutionEvent]:
        """List events for an execution."""
        return await self.execution_events.list_events(execution_id, event_type, skip, limit)

    async def create_outbox_event(self, event: OutboxEvent) -> OutboxEvent:
        """Create a new outbox event."""
        return await self.outbox.create(event)

    async def create_outbox_batch(self, events: List[OutboxEvent]) -> List[OutboxEvent]:
        """Create multiple outbox events."""
        return await self.outbox.create_batch(events)

    async def get_unpublished_outbox(self, limit: int = 100, max_retries: int = 5) -> List[OutboxEvent]:
        """Get unpublished outbox events ready for publishing."""
        return await self.outbox.get_unpublished(limit, max_retries)

    async def mark_outbox_published(self, event_ids: List[UUID]) -> int:
        """Mark outbox events as published."""
        return await self.outbox.mark_published(event_ids)