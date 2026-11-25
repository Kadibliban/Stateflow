"""
StateFlow Execution Repository

Data access layer for workflow executions, step executions, and compensations.
"""
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, update, delete, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.execution import (
    WorkflowExecution,
    StepExecution,
    CompensationExecution,
    ExecutionStatus,
    StepStatus,
)
from app.models.idempotency import IdempotencyRecord


class ExecutionRepository:
    """Repository for workflow execution operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, execution: WorkflowExecution) -> WorkflowExecution:
        """Create a new execution."""
        self.session.add(execution)
        await self.session.flush()
        await self.session.refresh(execution)
        return execution

    async def get_by_id(self, execution_id: UUID) -> Optional[WorkflowExecution]:
        """Get execution by ID."""
        result = await self.session.execute(
            select(WorkflowExecution).where(WorkflowExecution.id == execution_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_org(self, execution_id: UUID, org_id: UUID) -> Optional[WorkflowExecution]:
        """Get execution by ID and organization."""
        result = await self.session.execute(
            select(WorkflowExecution).where(
                WorkflowExecution.id == execution_id,
                WorkflowExecution.organization_id == org_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_with_steps(self, execution_id: UUID) -> Optional[WorkflowExecution]:
        """Get execution with step executions loaded."""
        result = await self.session.execute(
            select(WorkflowExecution)
            .options(selectinload(WorkflowExecution.step_executions))
            .where(WorkflowExecution.id == execution_id)
        )
        return result.scalar_one_or_none()

    async def get_with_all(self, execution_id: UUID) -> Optional[WorkflowExecution]:
        """Get execution with steps and compensations loaded."""
        result = await self.session.execute(
            select(WorkflowExecution)
            .options(
                selectinload(WorkflowExecution.step_executions),
                selectinload(WorkflowExecution.compensation_executions),
            )
            .where(WorkflowExecution.id == execution_id)
        )
        return result.scalar_one_or_none()

    async def update(self, execution: WorkflowExecution) -> WorkflowExecution:
        """Update execution."""
        await self.session.flush()
        await self.session.refresh(execution)
        return execution

    async def update_status(
        self,
        execution_id: UUID,
        status: ExecutionStatus,
        error: Optional[str] = None,
        error_details: Optional[dict] = None,
    ) -> bool:
        """Update execution status."""
        values = {"status": status, "updated_at": datetime.now(timezone.utc)}
        if error is not None:
            values["error"] = error
        if error_details is not None:
            values["error_details"] = error_details
        if status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED,
                      ExecutionStatus.COMPENSATED, ExecutionStatus.PARTIALLY_COMPENSATED,
                      ExecutionStatus.CANCELLED, ExecutionStatus.TIMED_OUT]:
            values["completed_at"] = datetime.now(timezone.utc)

        result = await self.session.execute(
            update(WorkflowExecution)
            .where(WorkflowExecution.id == execution_id)
            .values(**values)
        )
        return result.rowcount > 0

    async def list_executions(
        self,
        org_id: UUID,
        workflow_id: Optional[UUID] = None,
        status: Optional[ExecutionStatus] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[WorkflowExecution]:
        """List executions with filters."""
        query = select(WorkflowExecution).where(WorkflowExecution.organization_id == org_id)

        if workflow_id:
            query = query.where(WorkflowExecution.workflow_id == workflow_id)
        if status:
            query = query.where(WorkflowExecution.status == status)

        query = query.order_by(desc(WorkflowExecution.created_at)).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def count_executions(
        self,
        org_id: UUID,
        workflow_id: Optional[UUID] = None,
        status: Optional[ExecutionStatus] = None,
    ) -> int:
        """Count executions with filters."""
        query = select(func.count(WorkflowExecution.id)).where(WorkflowExecution.organization_id == org_id)

        if workflow_id:
            query = query.where(WorkflowExecution.workflow_id == workflow_id)
        if status:
            query = query.where(WorkflowExecution.status == status)

        result = await self.session.execute(query)
        return result.scalar() or 0

    async def get_pending_executions(self, limit: int = 100) -> List[WorkflowExecution]:
        """Get pending executions ready to run."""
        result = await self.session.execute(
            select(WorkflowExecution)
            .where(WorkflowExecution.status == ExecutionStatus.PENDING)
            .order_by(WorkflowExecution.created_at)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_running_executions(self, org_id: UUID) -> List[WorkflowExecution]:
        """Get running executions for organization."""
        result = await self.session.execute(
            select(WorkflowExecution).where(
                WorkflowExecution.organization_id == org_id,
                WorkflowExecution.status == ExecutionStatus.RUNNING,
            )
        )
        return result.scalars().all()


class StepExecutionRepository:
    """Repository for step execution operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, step_execution: StepExecution) -> StepExecution:
        """Create a new step execution."""
        self.session.add(step_execution)
        await self.session.flush()
        await self.session.refresh(step_execution)
        return step_execution

    async def get_by_id(self, step_execution_id: UUID) -> Optional[StepExecution]:
        """Get step execution by ID."""
        result = await self.session.execute(
            select(StepExecution).where(StepExecution.id == step_execution_id)
        )
        return result.scalar_one_or_none()

    async def get_by_execution_and_key(
        self, execution_id: UUID, step_key: str
    ) -> Optional[StepExecution]:
        """Get step execution by execution and step key."""
        result = await self.session.execute(
            select(StepExecution).where(
                StepExecution.execution_id == execution_id,
                StepExecution.step_key == step_key,
            )
        )
        return result.scalar_one_or_none()

    async def update(self, step_execution: StepExecution) -> StepExecution:
        """Update step execution."""
        await self.session.flush()
        await self.session.refresh(step_execution)
        return step_execution

    async def update_status(
        self,
        step_execution_id: UUID,
        status: StepStatus,
        output_data: Optional[dict] = None,
        error: Optional[str] = None,
        error_details: Optional[dict] = None,
        worker_id: Optional[str] = None,
    ) -> bool:
        """Update step execution status."""
        values = {"status": status}
        if output_data is not None:
            values["output_data"] = output_data
        if error is not None:
            values["error"] = error
        if error_details is not None:
            values["error_details"] = error_details
        if worker_id is not None:
            values["worker_id"] = worker_id

        if status == StepStatus.RUNNING:
            values["started_at"] = datetime.now(timezone.utc)
        elif status in [StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.SKIPPED,
                        StepStatus.COMPENSATED, StepStatus.COMPENSATION_FAILED,
                        StepStatus.CANCELLED]:
            values["completed_at"] = datetime.now(timezone.utc)

        result = await self.session.execute(
            update(StepExecution)
            .where(StepExecution.id == step_execution_id)
            .values(**values)
        )
        return result.rowcount > 0

    async def increment_attempt(self, step_execution_id: UUID) -> bool:
        """Increment attempt counter."""
        result = await self.session.execute(
            update(StepExecution)
            .where(StepExecution.id == step_execution_id)
            .values(attempt=StepExecution.attempt + 1)
        )
        return result.rowcount > 0

    async def schedule_retry(self, step_execution_id: UUID, next_retry_at: datetime) -> bool:
        """Schedule a retry for step execution."""
        result = await self.session.execute(
            update(StepExecution)
            .where(StepExecution.id == step_execution_id)
            .values(
                status=StepStatus.RETRYING,
                next_retry_at=next_retry_at,
                attempt=StepExecution.attempt + 1,
            )
        )
        return result.rowcount > 0

    async def list_step_executions(self, execution_id: UUID) -> List[StepExecution]:
        """List step executions for an execution."""
        result = await self.session.execute(
            select(StepExecution)
            .where(StepExecution.execution_id == execution_id)
            .order_by(StepExecution.started_at)
        )
        return result.scalars().all()

    async def get_retryable_steps(self, limit: int = 100) -> List[StepExecution]:
        """Get step executions ready for retry."""
        result = await self.session.execute(
            select(StepExecution)
            .where(
                StepExecution.status == StepStatus.RETRYING,
                StepExecution.next_retry_at <= datetime.now(timezone.utc),
            )
            .limit(limit)
        )
        return result.scalars().all()


class CompensationExecutionRepository:
    """Repository for compensation execution operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, compensation: CompensationExecution) -> CompensationExecution:
        """Create a new compensation execution."""
        self.session.add(compensation)
        await self.session.flush()
        await self.session.refresh(compensation)
        return compensation

    async def get_by_id(self, compensation_id: UUID) -> Optional[CompensationExecution]:
        """Get compensation execution by ID."""
        result = await self.session.execute(
            select(CompensationExecution).where(CompensationExecution.id == compensation_id)
        )
        return result.scalar_one_or_none()

    async def get_by_step_execution(self, step_execution_id: UUID) -> Optional[CompensationExecution]:
        """Get compensation execution by step execution ID."""
        result = await self.session.execute(
            select(CompensationExecution).where(
                CompensationExecution.step_execution_id == step_execution_id
            )
        )
        return result.scalar_one_or_none()

    async def update(self, compensation: CompensationExecution) -> CompensationExecution:
        """Update compensation execution."""
        await self.session.flush()
        await self.session.refresh(compensation)
        return compensation

    async def update_status(
        self,
        compensation_id: UUID,
        status: StepStatus,
        output_data: Optional[dict] = None,
        error: Optional[str] = None,
        error_details: Optional[dict] = None,
        worker_id: Optional[str] = None,
    ) -> bool:
        """Update compensation execution status."""
        values = {"status": status}
        if output_data is not None:
            values["output_data"] = output_data
        if error is not None:
            values["error"] = error
        if error_details is not None:
            values["error_details"] = error_details
        if worker_id is not None:
            values["worker_id"] = worker_id

        if status == StepStatus.COMPENSATING:
            values["started_at"] = datetime.now(timezone.utc)
        elif status in [StepStatus.COMPENSATED, StepStatus.COMPENSATION_FAILED, StepStatus.CANCELLED]:
            values["completed_at"] = datetime.now(timezone.utc)

        result = await self.session.execute(
            update(CompensationExecution)
            .where(CompensationExecution.id == compensation_id)
            .values(**values)
        )
        return result.rowcount > 0

    async def increment_attempt(self, compensation_id: UUID) -> bool:
        """Increment attempt counter."""
        result = await self.session.execute(
            update(CompensationExecution)
            .where(CompensationExecution.id == compensation_id)
            .values(attempt=CompensationExecution.attempt + 1)
        )
        return result.rowcount > 0

    async def schedule_retry(self, compensation_id: UUID, next_retry_at: datetime) -> bool:
        """Schedule a retry for compensation execution."""
        result = await self.session.execute(
            update(CompensationExecution)
            .where(CompensationExecution.id == compensation_id)
            .values(
                status=StepStatus.RETRYING,
                next_retry_at=next_retry_at,
                attempt=CompensationExecution.attempt + 1,
            )
        )
        return result.rowcount > 0

    async def list_compensations(self, execution_id: UUID) -> List[CompensationExecution]:
        """List compensation executions for an execution."""
        result = await self.session.execute(
            select(CompensationExecution)
            .where(CompensationExecution.execution_id == execution_id)
            .order_by(CompensationExecution.started_at)
        )
        return result.scalars().all()

    async def get_retryable_compensations(self, limit: int = 100) -> List[CompensationExecution]:
        """Get compensation executions ready for retry."""
        result = await self.session.execute(
            select(CompensationExecution)
            .where(
                CompensationExecution.status == StepStatus.RETRYING,
                CompensationExecution.next_retry_at <= datetime.now(timezone.utc),
            )
            .limit(limit)
        )
        return result.scalars().all()


class IdempotencyRepository:
    """Repository for idempotency record operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, record: IdempotencyRecord) -> IdempotencyRecord:
        """Create a new idempotency record."""
        self.session.add(record)
        await self.session.flush()
        await self.session.refresh(record)
        return record

    async def get_by_key(self, scope: str, idempotency_key: str) -> Optional[IdempotencyRecord]:
        """Get idempotency record by scope and key."""
        result = await self.session.execute(
            select(IdempotencyRecord).where(
                IdempotencyRecord.scope == scope,
                IdempotencyRecord.idempotency_key == idempotency_key,
            )
        )
        return result.scalar_one_or_none()

    async def get_valid_by_key(self, scope: str, idempotency_key: str) -> Optional[IdempotencyRecord]:
        """Get valid (non-expired) idempotency record."""
        result = await self.session.execute(
            select(IdempotencyRecord).where(
                IdempotencyRecord.scope == scope,
                IdempotencyRecord.idempotency_key == idempotency_key,
                IdempotencyRecord.expires_at > datetime.now(timezone.utc),
            )
        )
        return result.scalar_one_or_none()

    async def lock(self, record_id: UUID, lock_ttl_seconds: int = 30) -> bool:
        """Lock an idempotency record for processing."""
        result = await self.session.execute(
            update(IdempotencyRecord)
            .where(
                IdempotencyRecord.id == record_id,
                IdempotencyRecord.locked == False,
            )
            .values(
                locked=True,
                locked_at=datetime.now(timezone.utc),
                lock_expires_at=datetime.now(timezone.utc) +
                datetime.now(timezone.utc).replace(second=0, microsecond=0).__class__.fromtimestamp(
                    datetime.now(timezone.utc).timestamp() + lock_ttl_seconds
                ),
            )
        )
        return result.rowcount > 0

    async def complete(self, record_id: UUID, response_data: dict, status_code: int = 200) -> bool:
        """Mark idempotency record as completed."""
        result = await self.session.execute(
            update(IdempotencyRecord)
            .where(IdempotencyRecord.id == record_id)
            .values(
                completed=True,
                response_data=response_data,
                status_code=status_code,
                locked=False,
            )
        )
        return result.rowcount > 0

    async def release_lock(self, record_id: UUID) -> bool:
        """Release lock on idempotency record."""
        result = await self.session.execute(
            update(IdempotencyRecord)
            .where(IdempotencyRecord.id == record_id)
            .values(locked=False, locked_at=None, lock_expires_at=None)
        )
        return result.rowcount > 0

    async def cleanup_expired(self) -> int:
        """Delete expired idempotency records."""
        result = await self.session.execute(
            delete(IdempotencyRecord).where(IdempotencyRecord.expires_at < datetime.now(timezone.utc))
        )
        return result.rowcount