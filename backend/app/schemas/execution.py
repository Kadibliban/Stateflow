"""
StateFlow Execution Schemas

Pydantic models for workflow executions, step executions, and compensations.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ExecutionBase(BaseModel):
    """Base execution schema."""
    idempotency_key: Optional[str] = Field(None, max_length=255)
    input_data: Dict[str, Any] = Field(default_factory=dict)


class ExecutionCreate(ExecutionBase):
    """Execution creation request."""
    pass


class ExecutionResponse(ExecutionBase):
    """Execution response schema."""
    id: UUID
    workflow_id: UUID
    version_id: UUID
    organization_id: UUID
    status: str
    context: Dict[str, Any]
    output_data: Dict[str, Any]
    error: Optional[str]
    error_details: Dict[str, Any]
    current_step: Optional[str]
    completed_steps: List[str]
    failed_step: Optional[str]
    retry_count: int
    compensation_retry_count: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    triggered_by: Optional[UUID]
    correlation_id: Optional[str]

    class Config:
        from_attributes = True


class ExecutionListResponse(BaseModel):
    """Paginated execution list response."""
    items: List[ExecutionResponse]
    total: int
    skip: int
    limit: int


class StepExecutionResponse(BaseModel):
    """Step execution response schema."""
    id: UUID
    execution_id: UUID
    step_def_id: UUID
    step_key: str
    status: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    error: Optional[str]
    error_details: Dict[str, Any]
    attempt: int
    max_attempts: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    next_retry_at: Optional[datetime]
    duration_ms: Optional[int]
    worker_id: Optional[str]
    idempotency_key: Optional[str]

    class Config:
        from_attributes = True


class CompensationExecutionResponse(BaseModel):
    """Compensation execution response schema."""
    id: UUID
    execution_id: UUID
    step_execution_id: UUID
    step_key: str
    compensation_handler: str
    compensation_config: Dict[str, Any]
    status: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    error: Optional[str]
    error_details: Dict[str, Any]
    attempt: int
    max_attempts: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    next_retry_at: Optional[datetime]
    duration_ms: Optional[int]
    worker_id: Optional[str]
    idempotency_key: Optional[str]
    original_failure: Optional[str]

    class Config:
        from_attributes = True


class ExecutionDetailResponse(BaseModel):
    """Complete execution detail with steps and compensations."""
    execution: ExecutionResponse
    steps: List[StepExecutionResponse]
    compensations: List[CompensationExecutionResponse]