"""
StateFlow Execution Service

Business logic for workflow execution, step execution, and compensation.
"""
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.execution import (
    WorkflowExecution,
    StepExecution,
    CompensationExecution,
    ExecutionStatus,
    StepStatus,
)
from app.models.workflow import Workflow, WorkflowVersion, WorkflowStep
from app.models.organization import OrganizationMember, MemberRole
from app.models.idempotency import IdempotencyRecord
from app.repositories.execution_repository import (
    ExecutionRepository,
    StepExecutionRepository,
    CompensationExecutionRepository,
    IdempotencyRepository,
)
from app.repositories.workflow_repository import WorkflowRepository, WorkflowVersionRepository
from app.repositories.organization_repository import OrganizationMemberRepository
from app.repositories.event_repository import ExecutionEventRepository
from app.models.event import ExecutionEvent, EventType
from app.schemas.execution import (
    ExecutionResponse,
    ExecutionDetailResponse,
    StepExecutionResponse,
    CompensationExecutionResponse,
)


class ExecutionService:
    """Service for workflow execution operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.execution_repo = ExecutionRepository(session)
        self.step_repo = StepExecutionRepository(session)
        self.compensation_repo = CompensationExecutionRepository(session)
        self.idempotency_repo = IdempotencyRepository(session)
        self.workflow_repo = WorkflowRepository(session)
        self.version_repo = WorkflowVersionRepository(session)
        self.member_repo = OrganizationMemberRepository(session)
        self.event_repo = ExecutionEventRepository(session)

    async def start_execution(
        self,
        workflow_id: UUID,
        org_id: UUID,
        user_id: UUID,
        input_data: dict,
        idempotency_key: Optional[str] = None,
    ) -> ExecutionResponse:
        """Start a new workflow execution."""
        if not await self.member_repo.has_role(org_id, user_id, [MemberRole.OWNER, MemberRole.ADMINISTRATOR, MemberRole.DEVELOPER, MemberRole.VIEWER]):
            raise ValueError("Insufficient permissions")

        workflow = await self.workflow_repo.get_by_id_with_org(workflow_id, org_id)
        if not workflow:
            raise ValueError("Workflow not found")

        if workflow.status != WorkflowStatus.ACTIVE:
            raise ValueError("Workflow is not active")

        version = await self.version_repo.get_by_workflow_and_number(workflow_id, workflow.current_version)
        if not version:
            raise ValueError("Workflow version not found")

        # Check idempotency
        if idempotency_key:
            existing = await self.idempotency_repo.get_valid_by_key("execution", idempotency_key)
            if existing and existing.completed:
                # Return existing execution
                exec_id = existing.response_data.get("execution_id")
                if exec_id:
                    existing_exec = await self.execution_repo.get_by_id_with_org(UUID(exec_id), org_id)
                    if existing_exec:
                        return ExecutionResponse.model_validate(existing_exec)

        # Create execution
        execution = WorkflowExecution(
            workflow_id=workflow_id,
            version_id=version.id,
            organization_id=org_id,
            status=ExecutionStatus.PENDING,
            idempotency_key=idempotency_key,
            input_data=input_data,
            context={},
            output_data={},
            error_details={},
            completed_steps=[],
            triggered_by=user_id,
        )
        execution = await self.execution_repo.create(execution)
        await self.session.flush()

        # Create idempotency record if key provided
        if idempotency_key:
            idempotency = IdempotencyRecord(
                idempotency_key=idempotency_key,
                organization_id=org_id,
                scope="execution",
                request_hash="",
                response_data={"execution_id": str(execution.id)},
                completed=False,
                expires_at=datetime.now(timezone.utc) + timezone.timedelta(hours=24),
            )
            await self.idempotency_repo.create(idempotency)

        await self.session.commit()
        await self.session.refresh(execution)

        # Log event
        await self._log_event(
            execution_id=execution.id,
            event_type=EventType.EXECUTION_STARTED,
            message=f"Execution started for workflow {workflow.name}",
        )

        # TODO: Trigger async execution via Celery
        # For now, return the created execution

        return ExecutionResponse.model_validate(execution)

    async def get_execution(
        self,
        execution_id: UUID,
        org_id: UUID,
        user_id: UUID,
    ) -> ExecutionResponse:
        """Get execution by ID."""
        if not await self.member_repo.has_role(org_id, user_id, [MemberRole.OWNER, MemberRole.ADMINISTRATOR, MemberRole.DEVELOPER, MemberRole.VIEWER]):
            raise ValueError("Insufficient permissions")

        execution = await self.execution_repo.get_by_id_with_org(execution_id, org_id)
        if not execution:
            raise ValueError("Execution not found")

        return ExecutionResponse.model_validate(execution)

    async def get_execution_detail(
        self,
        execution_id: UUID,
        org_id: UUID,
        user_id: UUID,
    ) -> ExecutionDetailResponse:
        """Get execution with all steps and compensations."""
        if not await self.member_repo.has_role(org_id, user_id, [MemberRole.OWNER, MemberRole.ADMINISTRATOR, MemberRole.DEVELOPER, MemberRole.VIEWER]):
            raise ValueError("Insufficient permissions")

        execution = await self.execution_repo.get_with_all(execution_id)
        if not execution or execution.organization_id != org_id:
            raise ValueError("Execution not found")

        steps = await self.step_repo.list_step_executions(execution_id)
        compensations = await self.compensation_repo.list_compensations(execution_id)

        return ExecutionDetailResponse(
            execution=ExecutionResponse.model_validate(execution),
            steps=[StepExecutionResponse.model_validate(s) for s in steps],
            compensations=[CompensationExecutionResponse.model_validate(c) for c in compensations],
        )

    async def list_executions(
        self,
        org_id: UUID,
        user_id: UUID,
        workflow_id: Optional[UUID] = None,
        status: Optional[ExecutionStatus] = None,
        skip: int = 0,
        limit: int = 20,
    ):
        """List executions with filters."""
        if not await self.member_repo.has_role(org_id, user_id, [MemberRole.OWNER, MemberRole.ADMINISTRATOR, MemberRole.DEVELOPER, MemberRole.VIEWER]):
            raise ValueError("Insufficient permissions")

        executions = await self.execution_repo.list_executions(org_id, workflow_id, status, skip, limit)
        total = await self.execution_repo.count_executions(org_id, workflow_id, status)

        return {
            "items": [ExecutionResponse.model_validate(e) for e in executions],
            "total": total,
            "skip": skip,
            "limit": limit,
        }

    async def cancel_execution(
        self,
        execution_id: UUID,
        org_id: UUID,
        user_id: UUID,
    ) -> ExecutionResponse:
        """Cancel a running execution."""
        if not await self.member_repo.has_role(org_id, user_id, [MemberRole.OWNER, MemberRole.ADMINISTRATOR, MemberRole.DEVELOPER]):
            raise ValueError("Insufficient permissions")

        execution = await self.execution_repo.get_by_id_with_org(execution_id, org_id)
        if not execution:
            raise ValueError("Execution not found")

        if execution.status not in [ExecutionStatus.PENDING, ExecutionStatus.RUNNING]:
            raise ValueError("Can only cancel pending or running executions")

        await self.execution_repo.update_status(execution_id, ExecutionStatus.CANCELLED)
        await self.session.commit()

        await self._log_event(
            execution_id=execution_id,
            event_type=EventType.EXECUTION_CANCELLED,
            message="Execution cancelled by user",
        )

        execution = await self.execution_repo.get_by_id(execution_id)
        return ExecutionResponse.model_validate(execution)

    async def retry_execution(
        self,
        execution_id: UUID,
        org_id: UUID,
        user_id: UUID,
    ) -> ExecutionResponse:
        """Retry a failed execution."""
        if not await self.member_repo.has_role(org_id, user_id, [MemberRole.OWNER, MemberRole.ADMINISTRATOR, MemberRole.DEVELOPER]):
            raise ValueError("Insufficient permissions")

        execution = await self.execution_repo.get_by_id_with_org(execution_id, org_id)
        if not execution:
            raise ValueError("Execution not found")

        if execution.status not in [ExecutionStatus.FAILED, ExecutionStatus.COMPENSATED, ExecutionStatus.PARTIALLY_COMPENSATED]:
            raise ValueError("Can only retry failed or compensated executions")

        # Reset execution for retry
        execution.status = ExecutionStatus.PENDING
        execution.retry_count += 1
        execution.error = None
        execution.error_details = {}
        execution.current_step = None
        execution.completed_steps = []
        execution.failed_step = None
        execution.started_at = None
        execution.completed_at = None

        # Reset step executions
        await self.session.execute(
            select(StepExecution)
            .where(StepExecution.execution_id == execution_id)
        )
        # Actually update them
        from sqlalchemy import update
        await self.session.execute(
            update(StepExecution)
            .where(StepExecution.execution_id == execution_id)
            .values(
                status=StepStatus.PENDING,
                input_data={},
                output_data={},
                error=None,
                error_details={},
                attempt=1,
                started_at=None,
                completed_at=None,
                next_retry_at=None,
                duration_ms=None,
                worker_id=None,
            )
        )

        # Delete compensation executions
        from sqlalchemy import delete
        await self.session.execute(
            delete(CompensationExecution).where(CompensationExecution.execution_id == execution_id)
        )

        await self.session.commit()
        await self.session.refresh(execution)

        await self._log_event(
            execution_id=execution_id,
            event_type=EventType.RETRY_SCHEDULED,
            message="Execution retry initiated",
        )

        return ExecutionResponse.model_validate(execution)

    async def trigger_compensation(
        self,
        execution_id: UUID,
        org_id: UUID,
        user_id: UUID,
    ) -> ExecutionResponse:
        """Manually trigger compensation for a failed execution."""
        if not await self.member_repo.has_role(org_id, user_id, [MemberRole.OWNER, MemberRole.ADMINISTRATOR, MemberRole.DEVELOPER]):
            raise ValueError("Insufficient permissions")

        execution = await self.execution_repo.get_by_id_with_org(execution_id, org_id)
        if not execution:
            raise ValueError("Execution not found")

        if execution.status not in [ExecutionStatus.FAILED, ExecutionStatus.PARTIALLY_COMPENSATED]:
            raise ValueError("Can only compensate failed or partially compensated executions")

        execution.status = ExecutionStatus.COMPENSATING
        execution.compensation_retry_count = 0
        await self.session.commit()

        await self._log_event(
            execution_id=execution_id,
            event_type=EventType.COMPENSATION_STARTED,
            message="Manual compensation triggered",
        )

        # TODO: Trigger compensation via Celery

        execution = await self.execution_repo.get_by_id(execution_id)
        return ExecutionResponse.model_validate(execution)

    async def _log_event(
        self,
        execution_id: UUID,
        event_type: EventType,
        message: str,
        step_execution_id: Optional[UUID] = None,
        compensation_execution_id: Optional[UUID] = None,
        event_data: Optional[dict] = None,
    ) -> ExecutionEvent:
        """Log an execution event."""
        event = ExecutionEvent(
            execution_id=execution_id,
            step_execution_id=step_execution_id,
            compensation_execution_id=compensation_execution_id,
            event_type=event_type,
            event_data=event_data or {},
            message=message,
            severity="info",
        )
        return await self.event_repo.create(event)