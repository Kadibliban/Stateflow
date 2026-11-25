"""
StateFlow Execution Models

Workflow execution instances, step executions, and compensation tracking.
"""
import enum
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
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


class ExecutionStatus(str, enum.Enum):
    """Workflow execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    PARTIALLY_COMPENSATED = "partially_compensated"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class StepStatus(str, enum.Enum):
    """Step execution status."""
    PENDING = "pending"
    WAITING = "waiting"           # Waiting for dependencies
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    COMPENSATION_FAILED = "compensation_failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class WorkflowExecution(Base):
    """Workflow execution instance."""

    __tablename__ = "workflow_executions"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    workflow_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    version_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_versions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[ExecutionStatus] = mapped_column(
        Enum(
            ExecutionStatus,
            native_enum=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        default=ExecutionStatus.PENDING.value,
        nullable=False,
        index=True,
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    context: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    input_data: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    output_data: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    error_details: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    current_step: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    completed_steps: Mapped[List[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )
    failed_step: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    compensation_retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    triggered_by: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    correlation_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )

    # Relationships
    workflow: Mapped["Workflow"] = relationship(
        "Workflow",
        back_populates="executions",
    )
    version: Mapped["WorkflowVersion"] = relationship(
        "WorkflowVersion",
        back_populates="executions",
    )
    step_executions: Mapped[list["StepExecution"]] = relationship(
        "StepExecution",
        back_populates="execution",
        cascade="all, delete-orphan",
        order_by="StepExecution.started_at",
    )
    compensation_executions: Mapped[list["CompensationExecution"]] = relationship(
        "CompensationExecution",
        back_populates="execution",
        cascade="all, delete-orphan",
    )
    events: Mapped[list["ExecutionEvent"]] = relationship(
        "ExecutionEvent",
        back_populates="execution",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_executions_org_status_created", "organization_id", "status", "created_at"),
        Index("ix_executions_workflow_status", "workflow_id", "status"),
        Index("ix_executions_idempotency", "idempotency_key", unique=True),
    )

    def __repr__(self) -> str:
        return f"<WorkflowExecution(id={self.id}, workflow_id={self.workflow_id}, status={self.status})>"


class StepExecution(Base):
    """Individual step execution within a workflow."""

    __tablename__ = "step_executions"

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
    step_def_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_steps.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    step_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    status: Mapped[StepStatus] = mapped_column(
        Enum(
            StepStatus,
            native_enum=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        default=StepStatus.PENDING.value,
        nullable=False,
        index=True,
    )
    input_data: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    output_data: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    error_details: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    attempt: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer,
        default=3,
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    worker_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    # Relationships
    execution: Mapped["WorkflowExecution"] = relationship(
        "WorkflowExecution",
        back_populates="step_executions",
    )
    step_def: Mapped["WorkflowStep"] = relationship(
        "WorkflowStep",
        back_populates="executions",
    )
    compensation: Mapped["CompensationExecution | None"] = relationship(
        "CompensationExecution",
        back_populates="step_execution",
        uselist=False,
    )

    __table_args__ = (
        Index("ix_step_executions_execution_status", "execution_id", "status"),
        Index("ix_step_executions_step_def", "step_def_id"),
        Index("ix_step_executions_retry", "next_retry_at", "status"),
    )

    def __repr__(self) -> str:
        return f"<StepExecution(id={self.id}, step_key={self.step_key}, status={self.status})>"


class CompensationExecution(Base):
    """Compensation action execution tracking."""

    __tablename__ = "compensation_executions"

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
    step_execution_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("step_executions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    step_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    compensation_handler: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    compensation_config: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    status: Mapped[StepStatus] = mapped_column(
        Enum(
            StepStatus,
            native_enum=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        default=StepStatus.PENDING.value,
        nullable=False,
        index=True,
    )
    input_data: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    output_data: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    error_details: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    attempt: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer,
        default=3,
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    worker_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    original_failure: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    execution: Mapped["WorkflowExecution"] = relationship(
        "WorkflowExecution",
        back_populates="compensation_executions",
    )
    step_execution: Mapped["StepExecution"] = relationship(
        "StepExecution",
        back_populates="compensation",
    )

    __table_args__ = (
        Index("ix_compensation_executions_execution_status", "execution_id", "status"),
        Index("ix_compensation_executions_retry", "next_retry_at", "status"),
    )

    def __repr__(self) -> str:
        return f"<CompensationExecution(id={self.id}, step_key={self.step_key}, status={self.status})>"