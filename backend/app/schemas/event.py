"""
StateFlow Event Schemas

Pydantic models for execution events and event timelines.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ExecutionEventResponse(BaseModel):
    """Execution event response schema."""
    id: UUID
    execution_id: UUID
    step_execution_id: Optional[UUID]
    compensation_execution_id: Optional[UUID]
    event_type: str
    event_data: Dict[str, Any]
    message: Optional[str]
    severity: str
    created_at: datetime
    correlation_id: Optional[str]

    class Config:
        from_attributes = True


class EventTimelineResponse(BaseModel):
    """Complete event timeline for an execution."""
    execution_id: UUID
    events: List[ExecutionEventResponse]
    total: int


class EventSummary(BaseModel):
    """Event summary for dashboard."""
    event_type: str
    count: int
    last_occurrence: datetime