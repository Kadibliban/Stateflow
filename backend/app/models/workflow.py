"""
StateFlow Workflow Models

Workflow definitions, versions, and step definitions.
"""
import enum
import json
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
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class WorkflowStatus(str, enum.Enum):
    """Workflow definition status."""
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class StepType(str, enum.Enum):
    """Workflow step types."""
    ACTION = "action"           # Execute an action (HTTP call, function, etc.)
    CONDITION = "condition"     # Conditional branching
    PARALLEL = "parallel"       # Parallel execution group
    DELAY = "delay"             # Wait/delay step
    COMPENSATION = "compensation"  # Explicit compensation step


class RetryPolicy(Base):
    """Retry policy configuration for steps."""

    __tablename__ = "retry_policies"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer,
        default=3,
        nullable=False,
    )
    base_delay_seconds: Mapped[float] = mapped_column(
        default=1.0,
        nullable=False,
    )
    max_delay_seconds: Mapped[float] = mapped_column(
        default=60.0,
        nullable=False,
    )
    exponential_base: Mapped[float] = mapped_column(
        default=2.0,
        nullable=False,
    )
    retryable_errors: Mapped[List[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )
    non_retryable_errors: Mapped[List[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    steps: Mapped[list["WorkflowStep"]] = relationship(
        "WorkflowStep",
        back_populates="retry_policy",
    )

    def __repr__(self) -> str:
        return f"<RetryPolicy(id={self.id}, name={self.name}, max_attempts={self.max_attempts})>"


class Workflow(Base):
    """Workflow definition model."""

    __tablename__ = "workflows"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    organization_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    status: Mapped[WorkflowStatus] = mapped_column(
        Enum(
            WorkflowStatus,
            native_enum=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        default=WorkflowStatus.DRAFT.value,
        nullable=False,
    )
    current_version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    tags: Mapped[List[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )
    workflow_metadata: Mapped[Dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        nullable=False,
    )
    created_by: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
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
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    deprecated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="workflows",
    )
    versions: Mapped[list["WorkflowVersion"]] = relationship(
        "WorkflowVersion",
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="WorkflowVersion.version_number.desc()",
    )
    executions: Mapped[list["WorkflowExecution"]] = relationship(
        "WorkflowExecution",
        back_populates="workflow",
    )

    __table_args__ = (
        Index("ix_workflows_org_status", "organization_id", "status"),
        UniqueConstraint("organization_id", "name", name="uq_org_workflow_name"),
    )

    def __repr__(self) -> str:
        return f"<Workflow(id={self.id}, name={self.name}, status={self.status}, version={self.current_version})>"


class WorkflowVersion(Base):
    """Versioned workflow definition."""

    __tablename__ = "workflow_versions"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    workflow_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    definition: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    steps: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
    )
    connections: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )
    variables: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    created_by: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    changelog: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    workflow: Mapped["Workflow"] = relationship(
        "Workflow",
        back_populates="versions",
    )
    steps_def: Mapped[list["WorkflowStep"]] = relationship(
        "WorkflowStep",
        back_populates="version",
        cascade="all, delete-orphan",
        order_by="WorkflowStep.order",
    )
    executions: Mapped[list["WorkflowExecution"]] = relationship(
        "WorkflowExecution",
        back_populates="version",
    )

    __table_args__ = (
        UniqueConstraint("workflow_id", "version_number", name="uq_workflow_version"),
        Index("ix_workflow_versions_workflow_created", "workflow_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<WorkflowVersion(workflow_id={self.workflow_id}, version={self.version_number})>"


class WorkflowStep(Base):
    """Workflow step definition."""

    __tablename__ = "workflow_steps"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    version_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    step_type: Mapped[StepType] = mapped_column(
        Enum(
            StepType,
            native_enum=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        default=StepType.ACTION.value,
        nullable=False,
    )
    order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    handler: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    config: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    input_mapping: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    output_mapping: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    timeout_seconds: Mapped[int] = mapped_column(
        Integer,
        default=300,
        nullable=False,
    )
    retry_policy_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("retry_policies.id", ondelete="SET NULL"),
        nullable=True,
    )
    compensation_handler: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )
    compensation_config: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    depends_on: Mapped[List[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )
    is_critical: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    continue_on_failure: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
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

    # Relationships
    version: Mapped["WorkflowVersion"] = relationship(
        "WorkflowVersion",
        back_populates="steps_def",
    )
    retry_policy: Mapped[Optional["RetryPolicy"]] = relationship(
        "RetryPolicy",
        back_populates="steps",
    )
    executions: Mapped[list["StepExecution"]] = relationship(
        "StepExecution",
        back_populates="step_def",
    )

    __table_args__ = (
        UniqueConstraint("version_id", "step_key", name="uq_version_step_key"),
        Index("ix_workflow_steps_version_order", "version_id", "order"),
    )

    def __repr__(self) -> str:
        return f"<WorkflowStep(id={self.id}, key={self.step_key}, type={self.step_type})>"