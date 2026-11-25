"""
StateFlow Worker Schemas

Pydantic models for worker monitoring.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class WorkerHeartbeatResponse(BaseModel):
    """Worker heartbeat response schema."""
    id: UUID
    worker_id: str
    worker_type: str
    hostname: str
    pid: int
    status: str
    capabilities: List[str]
    current_executions: int
    max_concurrency: int
    metadata: Dict[str, Any]
    last_heartbeat_at: datetime
    started_at: datetime
    last_seen_at: datetime

    class Config:
        from_attributes = True


class WorkerHealthResponse(BaseModel):
    """Worker health summary."""
    total_workers: int
    healthy_workers: int
    unhealthy_workers: int
    total_capacity: int
    current_load: int
    workers: List[WorkerHeartbeatResponse]