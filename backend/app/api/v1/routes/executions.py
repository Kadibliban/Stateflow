"""
StateFlow Execution Routes

Workflow execution management, monitoring, and control.
"""
from typing import Annotated, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_session
from app.models.execution import (
    WorkflowExecution,
    StepExecution,
    CompensationExecution,
    ExecutionStatus,
    StepStatus,
)
from app.models.workflow import Workflow, WorkflowVersion, WorkflowStatus
from app.models.organization import OrganizationMember, MemberRole
from app.models.user import User
from app.schemas.execution import (
    ExecutionCreate,
    ExecutionResponse,
    ExecutionListResponse,
    StepExecutionResponse,
    CompensationExecutionResponse,
    ExecutionDetailResponse,
)
from app.api.v1.routes.auth import get_current_user

router = APIRouter()


# Dependency to check organization membership
async def get_org_membership(
    org_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    required_roles: List[MemberRole] | None = None,
) -> OrganizationMember:
    """Get and validate organization membership."""
    query = select(OrganizationMember).where(
        OrganizationMember.organization_id == org_id,
        OrganizationMember.user_id == current_user.id,
        OrganizationMember.is_active == True,
    )
    if required_roles:
        query = query.where(OrganizationMember.role_name.in_(required_roles))

    membership = await session.execute(query)
    membership = membership.scalar_one_or_none()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return membership


@router.post("", response_model=ExecutionResponse, status_code=status.HTTP_201_CREATED)
async def create_execution(
    workflow_id: UUID,
    request: ExecutionCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
) -> ExecutionResponse:
    """Start a new workflow execution."""
    # Check membership (viewer or above)
    await get_org_membership(org_id, current_user, session)

    # Get workflow
    workflow = await session.get(Workflow, workflow_id)
    if not workflow or workflow.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    if workflow.status != WorkflowStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workflow is not active",
        )

    # Get current version
    version = await session.execute(
        select(WorkflowVersion).where(
            WorkflowVersion.workflow_id == workflow_id,
            WorkflowVersion.version_number == workflow.current_version,
        )
    )
    version = version.scalar_one_or_none()
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow version not found",
        )

    # Check idempotency
    if request.idempotency_key:
        from app.models.idempotency import IdempotencyRecord
        existing = await session.execute(
            select(IdempotencyRecord).where(
                IdempotencyRecord.idempotency_key == request.idempotency_key,
                IdempotencyRecord.scope == "execution",
                IdempotencyRecord.organization_id == org_id,
            )
        )
        existing = existing.scalar_one_or_none()
        if existing:
            if existing.completed:
                # Return existing execution
                exec_result = await session.execute(
                    select(WorkflowExecution).where(WorkflowExecution.id == existing.response_data.get("execution_id"))
                )
                existing_exec = exec_result.scalar_one_or_none()
                if existing_exec:
                    return ExecutionResponse.model_validate(existing_exec)
            # If idempotency record exists but not completed, or execution not found,
            # don't create a new execution to avoid unique constraint violation
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Execution with this idempotency key already exists or is being processed",
            )

    # Create execution
    execution = WorkflowExecution(
        workflow_id=workflow_id,
        version_id=version.id,
        organization_id=org_id,
        status=ExecutionStatus.PENDING,
        idempotency_key=request.idempotency_key,
        input_data=request.input_data,
        context={},
        output_data={},
        error_details={},
        completed_steps=[],
        triggered_by=current_user.id,
    )
    session.add(execution)
    await session.flush()

    # Create idempotency record if key provided
    if request.idempotency_key:
        from app.models.idempotency import IdempotencyRecord
        from datetime import datetime, timezone, timedelta
        idempotency = IdempotencyRecord(
            idempotency_key=request.idempotency_key,
            organization_id=org_id,
            scope="execution",
            request_hash="",  # Could hash the request
            response_data={"execution_id": str(execution.id)},
            completed=False,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        session.add(idempotency)

    await session.commit()
    await session.refresh(execution)

    # Trigger async execution via Celery
    from app.workers.execution_tasks import execute_workflow
    execute_workflow.delay(str(execution.id))

    return ExecutionResponse.model_validate(execution)


@router.get("", response_model=ExecutionListResponse)
async def list_executions(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
    workflow_id: UUID | None = Query(None, description="Filter by workflow"),
    status: str | None = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> ExecutionListResponse:
    """List workflow executions."""
    await get_org_membership(org_id, current_user, session)

    query = select(WorkflowExecution).where(WorkflowExecution.organization_id == org_id)

    if workflow_id:
        query = query.where(WorkflowExecution.workflow_id == workflow_id)
    if status:
        query = query.where(WorkflowExecution.status == ExecutionStatus(status))

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await session.execute(count_query)
    total = total.scalar() or 0

    # Get paginated results
    query = query.order_by(desc(WorkflowExecution.created_at)).offset(skip).limit(limit)
    executions = await session.execute(query)
    executions = executions.scalars().all()

    return ExecutionListResponse(
        items=[ExecutionResponse.model_validate(e) for e in executions],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{execution_id}", response_model=ExecutionResponse)
async def get_execution(
    execution_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
) -> ExecutionResponse:
    """Get execution by ID."""
    await get_org_membership(org_id, current_user, session)

    execution = await session.get(WorkflowExecution, execution_id)
    if not execution or execution.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found",
        )

    return ExecutionResponse.model_validate(execution)


@router.get("/{execution_id}/detail", response_model=ExecutionDetailResponse)
async def get_execution_detail(
    execution_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
) -> ExecutionDetailResponse:
    """Get execution with all steps and compensations."""
    await get_org_membership(org_id, current_user, session)

    execution = await session.get(WorkflowExecution, execution_id)
    if not execution or execution.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found",
        )

    # Get step executions
    steps = await session.execute(
        select(StepExecution)
        .where(StepExecution.execution_id == execution_id)
        .order_by(StepExecution.started_at)
    )
    steps = steps.scalars().all()

    # Get compensation executions
    compensations = await session.execute(
        select(CompensationExecution)
        .where(CompensationExecution.execution_id == execution_id)
        .order_by(CompensationExecution.started_at)
    )
    compensations = compensations.scalars().all()

    return ExecutionDetailResponse(
        execution=ExecutionResponse.model_validate(execution),
        steps=[StepExecutionResponse.model_validate(s) for s in steps],
        compensations=[CompensationExecutionResponse.model_validate(c) for c in compensations],
    )


@router.get("/{execution_id}/steps", response_model=List[StepExecutionResponse])
async def list_execution_steps(
    execution_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
) -> List[StepExecutionResponse]:
    """List step executions for an execution."""
    await get_org_membership(org_id, current_user, session)

    execution = await session.get(WorkflowExecution, execution_id)
    if not execution or execution.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found",
        )

    steps = await session.execute(
        select(StepExecution)
        .where(StepExecution.execution_id == execution_id)
        .order_by(StepExecution.started_at)
    )
    steps = steps.scalars().all()

    return [StepExecutionResponse.model_validate(s) for s in steps]


@router.get("/{execution_id}/compensations", response_model=List[CompensationExecutionResponse])
async def list_execution_compensations(
    execution_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
) -> List[CompensationExecutionResponse]:
    """List compensation executions for an execution."""
    await get_org_membership(org_id, current_user, session)

    execution = await session.get(WorkflowExecution, execution_id)
    if not execution or execution.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found",
        )

    compensations = await session.execute(
        select(CompensationExecution)
        .where(CompensationExecution.execution_id == execution_id)
        .order_by(CompensationExecution.started_at)
    )
    compensations = compensations.scalars().all()

    return [CompensationExecutionResponse.model_validate(c) for c in compensations]


@router.post("/{execution_id}/cancel", response_model=ExecutionResponse)
async def cancel_execution(
    execution_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
) -> ExecutionResponse:
    """Cancel a running execution."""
    await get_org_membership(org_id, current_user, session, [MemberRole.OWNER, MemberRole.ADMINISTRATOR, MemberRole.DEVELOPER])

    execution = await session.get(WorkflowExecution, execution_id)
    if not execution or execution.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found",
        )

    if execution.status not in [ExecutionStatus.PENDING, ExecutionStatus.RUNNING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only cancel pending or running executions",
        )

    execution.status = ExecutionStatus.CANCELLED
    from datetime import datetime, timezone
    execution.completed_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(execution)

    return ExecutionResponse.model_validate(execution)


@router.post("/{execution_id}/retry", response_model=ExecutionResponse, status_code=status.HTTP_201_CREATED)
async def retry_execution(
    execution_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
) -> ExecutionResponse:
    """Retry a failed execution by creating a new execution record."""
    await get_org_membership(org_id, current_user, session, [MemberRole.OWNER, MemberRole.ADMINISTRATOR, MemberRole.DEVELOPER])

    original_execution = await session.get(WorkflowExecution, execution_id)
    if not original_execution or original_execution.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found",
        )

    if original_execution.status not in [ExecutionStatus.FAILED, ExecutionStatus.COMPENSATED, ExecutionStatus.PARTIALLY_COMPENSATED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only retry failed or compensated executions",
        )

    # Get the workflow and version from original execution
    workflow = await session.get(Workflow, original_execution.workflow_id)
    version = await session.get(WorkflowVersion, original_execution.version_id)

    if not workflow or not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow or version not found",
        )

    # Create new execution record for retry (preserves original for audit trail)
    new_execution = WorkflowExecution(
        workflow_id=workflow.id,
        version_id=version.id,
        organization_id=org_id,
        status=ExecutionStatus.PENDING,
        idempotency_key=None,  # No idempotency for retries to allow multiple retries
        input_data=original_execution.input_data,
        context={},
        output_data={},
        error_details={},
        completed_steps=[],
        triggered_by=current_user.id,
        retry_count=original_execution.retry_count + 1,  # Track retry number
    )
    session.add(new_execution)
    await session.flush()

    await session.commit()
    await session.refresh(new_execution)

    # Trigger async execution via Celery
    from app.workers.execution_tasks import execute_workflow
    execute_workflow.delay(str(new_execution.id))

    return ExecutionResponse.model_validate(new_execution)


@router.post("/{execution_id}/compensate", response_model=ExecutionResponse)
async def trigger_compensation(
    execution_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
) -> ExecutionResponse:
    """Manually trigger compensation for a failed execution."""
    await get_org_membership(org_id, current_user, session, [MemberRole.OWNER, MemberRole.ADMINISTRATOR, MemberRole.DEVELOPER])

    execution = await session.get(WorkflowExecution, execution_id)
    if not execution or execution.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found",
        )

    if execution.status not in [ExecutionStatus.FAILED, ExecutionStatus.PARTIALLY_COMPENSATED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only compensate failed or partially compensated executions",
        )

    # Reset compensation retry count (SagaEngine will set status to COMPENSATING)
    execution.compensation_retry_count = 0
    await session.commit()
    await session.refresh(execution)

    # Trigger saga compensation via Celery
    from app.workers.execution_tasks import execute_saga_compensation
    execute_saga_compensation.delay(str(execution.id))

    return ExecutionResponse.model_validate(execution)