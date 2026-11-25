"""
StateFlow Workflow Schemas

Pydantic models for workflow definitions, versions, and steps.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class WorkflowStepBase(BaseModel):
    """Base workflow step schema."""
    step_key: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    step_type: str = Field(..., pattern="^(action|condition|parallel|delay|compensation)$")
    order: int = Field(0, ge=0)
    handler: str = Field(..., min_length=1, max_length=200)
    config: Dict[str, Any] = Field(default_factory=dict)
    input_mapping: Dict[str, Any] = Field(default_factory=dict)
    output_mapping: Dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = Field(300, ge=1, le=3600)
    retry_policy_id: Optional[UUID] = None
    compensation_handler: Optional[str] = Field(None, max_length=200)
    compensation_config: Dict[str, Any] = Field(default_factory=dict)
    depends_on: List[str] = Field(default_factory=list)
    is_critical: bool = True
    continue_on_failure: bool = False


class WorkflowStepCreate(WorkflowStepBase):
    """Workflow step creation request."""
    pass


class WorkflowStepUpdate(BaseModel):
    """Workflow step update request."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    order: Optional[int] = Field(None, ge=0)
    handler: Optional[str] = Field(None, min_length=1, max_length=200)
    config: Optional[Dict[str, Any]] = None
    input_mapping: Optional[Dict[str, Any]] = None
    output_mapping: Optional[Dict[str, Any]] = None
    timeout_seconds: Optional[int] = Field(None, ge=1, le=3600)
    retry_policy_id: Optional[UUID] = None
    compensation_handler: Optional[str] = Field(None, max_length=200)
    compensation_config: Optional[Dict[str, Any]] = None
    depends_on: Optional[List[str]] = None
    is_critical: Optional[bool] = None
    continue_on_failure: Optional[bool] = None


class WorkflowStepResponse(WorkflowStepBase):
    """Workflow step response schema."""
    id: UUID
    version_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RetryPolicyBase(BaseModel):
    """Base retry policy schema."""
    name: str = Field(..., min_length=1, max_length=100)
    max_attempts: int = Field(3, ge=1, le=10)
    base_delay_seconds: float = Field(1.0, ge=0.1, le=60.0)
    max_delay_seconds: float = Field(60.0, ge=1.0, le=3600.0)
    exponential_base: float = Field(2.0, ge=1.0, le=10.0)
    retryable_errors: List[str] = Field(default_factory=list)
    non_retryable_errors: List[str] = Field(default_factory=list)


class RetryPolicyCreate(RetryPolicyBase):
    """Retry policy creation request."""
    pass


class RetryPolicyResponse(RetryPolicyBase):
    """Retry policy response schema."""
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class WorkflowBase(BaseModel):
    """Base workflow schema."""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    workflow_metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkflowCreate(WorkflowBase):
    """Workflow creation request."""
    pass


class WorkflowUpdate(BaseModel):
    """Workflow update request."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    workflow_metadata: Optional[Dict[str, Any]] = None


class WorkflowResponse(WorkflowBase):
    """Workflow response schema."""
    id: UUID
    organization_id: UUID
    status: str
    current_version: int
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    activated_at: Optional[datetime]
    deprecated_at: Optional[datetime]

    class Config:
        from_attributes = True


class WorkflowVersionResponse(BaseModel):
    """Workflow version response schema."""
    id: UUID
    workflow_id: UUID
    version_number: int
    definition: Dict[str, Any]
    steps: List[Dict[str, Any]]
    connections: List[Dict[str, Any]]
    variables: Dict[str, Any]
    created_by: UUID
    created_at: datetime
    changelog: Optional[str]
    steps_detail: List[WorkflowStepResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class WorkflowDefinition(BaseModel):
    """Complete workflow definition for visual editor."""
    workflow: WorkflowResponse
    version: WorkflowVersionResponse
    steps: List[WorkflowStepResponse]
    retry_policies: List[RetryPolicyResponse] = Field(default_factory=list)