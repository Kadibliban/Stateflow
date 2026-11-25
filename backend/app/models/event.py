"""
StateFlow Event Models

Event logging and transactional outbox for reliable event publishing.
"""
import enum
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class EventType(str, enum.Enum):
    """Execution event types."""
    # Workflow events
    WORKFLOW_CREATED = "workflow_created"
    WORKFLOW_ACTIVATED = "workflow_activated"
    WORKFLOW_DEACTIVATED = "workflow_deactivated"
    WORKFLOW_DEPRECATED = "workflow_deprecated"

    # Execution events
    EXECUTION_STARTED = "execution_started"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_FAILED = "execution_failed"
    EXECUTION_CANCELLED = "execution_cancelled"
    EXECUTION_TIMED_OUT = "execution_timed_out"

    # Step events
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    STEP_SKIPPED = "step_skipped"
    STEP_RETRYING = "step_retrying"
    STEP_RETRY_EXHAUSTED = "step_retry_exhausted"

    # Compensation events
    COMPENSATION_STARTED = "compensation_started"
    COMPENSATION_COMPLETED = "compensation_completed"
    COMPENSATION_FAILED = "compensation_failed"
    COMPENSATION_RETRYING = "compensation_retrying"
    COMPENSATION_RETRY_EXHAUSTED = "compensation_retry_exhausted"

    # Retry events
    RETRY_SCHEDULED = "retry_scheduled"
    RETRY_EXECUTED = "retry_executed"


class ExecutionEvent(Base):
    """Event log for workflow executions."""

    __tablename__ = "execution_events"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    execution_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_execution_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("step_executions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    compensation_execution_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("compensation_executions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[EventType] = mapped_column(
        Enum(
            EventType,
            native_enum=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        index=True,
    )
    event_data: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    severity: Mapped[str] = mapped_column(
        String(20),
        default="info",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    correlation_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )

    # Relationships
    execution: Mapped["WorkflowExecution"] = relationship(
        "WorkflowExecution",
        back_populates="events",
    )

    __table_args__ = (
        Index("ix_execution_events_execution_created", "execution_id", "created_at"),
        Index("ix_execution_events_type_created", "event_type", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ExecutionEvent(id={self.id}, type={self.event_type}, execution_id={self.execution_id})>"


class OutboxEvent(Base):
    """Transactional outbox for reliable event publishing."""

    __tablename__ = "outbox_events"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    aggregate_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    aggregate_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    payload: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    headers: Mapped[Dict[str, str]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    max_retries: Mapped[int] = mapped_column(
        Integer,
        default=5,
        nullable=False,
    )
    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    published: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    __table_args__ = (
        Index("ix_outbox_unpublished", "published", "next_retry_at"),
        Index("ix_outbox_aggregate", "aggregate_type", "aggregate_id"),
    )

    def __repr__(self) -> str:
        return f"<OutboxEvent(id={self.id}, type={self.event_type}, published={self.published})>"