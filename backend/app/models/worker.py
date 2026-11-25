"""
StateFlow Worker Models

Worker heartbeat and health tracking.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class WorkerHeartbeat(Base):
    """Worker heartbeat for health monitoring."""

    __tablename__ = "worker_heartbeats"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    worker_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )
    worker_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    hostname: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    pid: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="healthy",
        nullable=False,
    )
    capabilities: Mapped[List[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )
    current_executions: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    max_concurrency: Mapped[int] = mapped_column(
        Integer,
        default=4,
        nullable=False,
    )
    worker_metadata: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    last_heartbeat_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_worker_heartbeat_status", "status", "last_heartbeat_at"),
    )

    def __repr__(self) -> str:
        return f"<WorkerHeartbeat(worker_id={self.worker_id}, status={self.status})>"