"""
StateFlow Monitoring Schemas

Pydantic models for metrics and monitoring.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class MetricsSummary(BaseModel):
    """Overall metrics summary."""
    total_workflows: int
    total_executions: int
    successful_executions: int
    failed_executions: int
    running_executions: int
    success_rate: float
    avg_execution_duration_ms: float
    total_retries: int
    total_compensations: int


class ExecutionMetrics(BaseModel):
    """Execution metrics over time."""
    period: str
    total: int
    successful: int
    failed: int
    avg_duration_ms: float


class FailureMetrics(BaseModel):
    """Failure metrics."""
    total_failures: int
    by_step: Dict[str, int]
    by_error_type: Dict[str, int]
    retry_exhausted: int
    compensation_failures: int


class WorkflowMetrics(BaseModel):
    """Per-workflow metrics."""
    workflow_id: UUID
    workflow_name: str
    total_executions: int
    successful: int
    failed: int
    success_rate: float
    avg_duration_ms: float
    last_execution: Optional[datetime]


class SystemMetrics(BaseModel):
    """System-level metrics."""
    cpu_usage_percent: float
    memory_usage_percent: float
    disk_usage_percent: float
    db_connections_active: int
    db_connections_idle: int
    queue_depth: int
    active_workers: int