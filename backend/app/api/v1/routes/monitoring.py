"""
StateFlow Monitoring Routes

Metrics and monitoring endpoints.
"""
from typing import Annotated, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.execution import WorkflowExecution, ExecutionStatus
from app.models.workflow import Workflow
from app.models.organization import OrganizationMember, MemberRole
from app.models.user import User
from app.schemas.monitoring import (
    MetricsSummary,
    ExecutionMetrics,
    FailureMetrics,
    WorkflowMetrics,
    SystemMetrics,
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


@router.get("/summary", response_model=MetricsSummary)
async def get_metrics_summary(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
) -> MetricsSummary:
    """Get overall metrics summary."""
    await get_org_membership(org_id, current_user, session)

    # Total workflows
    total_workflows = await session.execute(
        select(func.count(Workflow.id)).where(Workflow.organization_id == org_id)
    )
    total_workflows = total_workflows.scalar() or 0

    # Execution counts
    exec_query = select(
        func.count(WorkflowExecution.id),
        func.sum(case((WorkflowExecution.status == ExecutionStatus.COMPLETED, 1), else_=0)),
        func.sum(case((WorkflowExecution.status == ExecutionStatus.FAILED, 1), else_=0)),
        func.sum(case((WorkflowExecution.status == ExecutionStatus.RUNNING, 1), else_=0)),
        func.avg(
            case(
                (
                    (WorkflowExecution.completed_at.isnot(None) & WorkflowExecution.started_at.isnot(None)),
                    (WorkflowExecution.completed_at - WorkflowExecution.started_at).total_seconds() * 1000,
                ),
                else_=None,
            )
        ),
    ).where(WorkflowExecution.organization_id == org_id)
    exec_result = await session.execute(exec_query)
    exec_row = exec_result.one()

    total_executions = exec_row[0] or 0
    successful = exec_row[1] or 0
    failed = exec_row[2] or 0
    running = exec_row[3] or 0
    avg_duration = exec_row[4] or 0.0

    success_rate = (successful / total_executions * 100) if total_executions > 0 else 0.0

    # Total retries
    from app.models.execution import StepExecution
    retries = await session.execute(
        select(func.sum(StepExecution.attempt - 1)).where(
            StepExecution.execution_id.in_(
                select(WorkflowExecution.id).where(WorkflowExecution.organization_id == org_id)
            )
        )
    )
    total_retries = retries.scalar() or 0

    # Total compensations
    from app.models.execution import CompensationExecution
    compensations = await session.execute(
        select(func.count(CompensationExecution.id)).where(
            CompensationExecution.execution_id.in_(
                select(WorkflowExecution.id).where(WorkflowExecution.organization_id == org_id)
            )
        )
    )
    total_compensations = compensations.scalar() or 0

    return MetricsSummary(
        total_workflows=total_workflows,
        total_executions=total_executions,
        successful_executions=successful,
        failed_executions=failed,
        running_executions=running,
        success_rate=round(success_rate, 2),
        avg_execution_duration_ms=round(avg_duration, 2),
        total_retries=total_retries,
        total_compensations=total_compensations,
    )


@router.get("/executions", response_model=List[ExecutionMetrics])
async def get_execution_metrics(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
    period: str = Query("day", pattern="^(hour|day|week|month)$"),
    limit: int = Query(30, ge=1, le=100),
) -> List[ExecutionMetrics]:
    """Get execution metrics over time."""
    await get_org_membership(org_id, current_user, session)

    from datetime import datetime, timezone, timedelta
    from sqlalchemy import text

    now = datetime.now(timezone.utc)
    if period == "hour":
        interval = timedelta(hours=1)
        trunc = "hour"
    elif period == "day":
        interval = timedelta(days=1)
        trunc = "day"
    elif period == "week":
        interval = timedelta(weeks=1)
        trunc = "week"
    else:
        interval = timedelta(days=30)
        trunc = "month"

    # Use raw SQL for time-series aggregation
    query = text(f"""
        SELECT
            date_trunc('{trunc}', created_at) as period,
            COUNT(*) as total,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as successful,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
            AVG(
                CASE
                    WHEN completed_at IS NOT NULL AND started_at IS NOT NULL
                    THEN EXTRACT(EPOCH FROM (completed_at - started_at)) * 1000
                END
            ) as avg_duration_ms
        FROM workflow_executions
        WHERE organization_id = :org_id
        AND created_at >= :since
        GROUP BY date_trunc('{trunc}', created_at)
        ORDER BY period DESC
        LIMIT :limit
    """)

    result = await session.execute(
        query,
        {"org_id": str(org_id), "since": now - interval * limit, "limit": limit},
    )
    rows = result.all()

    return [
        ExecutionMetrics(
            period=row[0].isoformat() if row[0] else "",
            total=row[1] or 0,
            successful=row[2] or 0,
            failed=row[3] or 0,
            avg_duration_ms=round(row[4] or 0.0, 2),
        )
        for row in rows
    ]


@router.get("/failures", response_model=FailureMetrics)
async def get_failure_metrics(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
) -> FailureMetrics:
    """Get failure metrics."""
    await get_org_membership(org_id, current_user, session)

    # Total failures
    total_failures = await session.execute(
        select(func.count(WorkflowExecution.id)).where(
            WorkflowExecution.organization_id == org_id,
            WorkflowExecution.status == ExecutionStatus.FAILED,
        )
    )
    total_failures = total_failures.scalar() or 0

    # Failures by step
    from app.models.execution import StepExecution, StepStatus
    step_failures = await session.execute(
        select(StepExecution.step_key, func.count(StepExecution.id))
        .where(
            StepExecution.execution_id.in_(
                select(WorkflowExecution.id).where(WorkflowExecution.organization_id == org_id)
            ),
            StepExecution.status == StepStatus.FAILED,
        )
        .group_by(StepExecution.step_key)
    )
    by_step = {row[0]: row[1] for row in step_failures.all()}

    # Failures by error type (simplified)
    error_failures = await session.execute(
        select(WorkflowExecution.error, func.count(WorkflowExecution.id))
        .where(
            WorkflowExecution.organization_id == org_id,
            WorkflowExecution.status == ExecutionStatus.FAILED,
            WorkflowExecution.error.isnot(None),
        )
        .group_by(WorkflowExecution.error)
    )
    by_error_type = {row[0] or "Unknown": row[1] for row in error_failures.all()}

    # Retry exhausted
    retry_exhausted = await session.execute(
        select(func.count(StepExecution.id)).where(
            StepExecution.execution_id.in_(
                select(WorkflowExecution.id).where(WorkflowExecution.organization_id == org_id)
            ),
            StepExecution.attempt >= StepExecution.max_attempts,
            StepExecution.status == StepStatus.FAILED,
        )
    )
    retry_exhausted = retry_exhausted.scalar() or 0

    # Compensation failures
    from app.models.execution import CompensationExecution
    compensation_failures = await session.execute(
        select(func.count(CompensationExecution.id)).where(
            CompensationExecution.execution_id.in_(
                select(WorkflowExecution.id).where(WorkflowExecution.organization_id == org_id)
            ),
            CompensationExecution.status == StepStatus.COMPENSATION_FAILED,
        )
    )
    compensation_failures = compensation_failures.scalar() or 0

    return FailureMetrics(
        total_failures=total_failures,
        by_step=by_step,
        by_error_type=by_error_type,
        retry_exhausted=retry_exhausted,
        compensation_failures=compensation_failures,
    )


@router.get("/workflows", response_model=List[WorkflowMetrics])
async def get_workflow_metrics(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
    limit: int = Query(20, ge=1, le=100),
) -> List[WorkflowMetrics]:
    """Get per-workflow metrics."""
    await get_org_membership(org_id, current_user, session)

    # Get workflow execution stats
    query = (
        select(
            Workflow.id,
            Workflow.name,
            func.count(WorkflowExecution.id),
            func.sum(case((WorkflowExecution.status == ExecutionStatus.COMPLETED, 1), else_=0)),
            func.sum(case((WorkflowExecution.status == ExecutionStatus.FAILED, 1), else_=0)),
            func.avg(
                case(
                    (
                        (WorkflowExecution.completed_at.isnot(None) & WorkflowExecution.started_at.isnot(None)),
                        (WorkflowExecution.completed_at - WorkflowExecution.started_at).total_seconds() * 1000,
                    ),
                    else_=None,
                )
            ),
            func.max(WorkflowExecution.created_at),
        )
        .join(WorkflowExecution, WorkflowExecution.workflow_id == Workflow.id)
        .where(Workflow.organization_id == org_id)
        .group_by(Workflow.id, Workflow.name)
        .order_by(func.count(WorkflowExecution.id).desc())
        .limit(limit)
    )

    result = await session.execute(query)
    rows = result.all()

    return [
        WorkflowMetrics(
            workflow_id=row[0],
            workflow_name=row[1],
            total_executions=row[2] or 0,
            successful=row[3] or 0,
            failed=row[4] or 0,
            success_rate=round((row[3] or 0) / (row[2] or 1) * 100, 2) if row[2] else 0.0,
            avg_duration_ms=round(row[5] or 0.0, 2),
            last_execution=row[6],
        )
        for row in rows
    ]


@router.get("/system", response_model=SystemMetrics)
async def get_system_metrics(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
) -> SystemMetrics:
    """Get system-level metrics (placeholder - would integrate with actual monitoring)."""
    await get_org_membership(org_id, current_user, session)

    # These would come from actual monitoring systems
    # For now, return placeholder values
    return SystemMetrics(
        cpu_usage_percent=0.0,
        memory_usage_percent=0.0,
        disk_usage_percent=0.0,
        db_connections_active=0,
        db_connections_idle=0,
        queue_depth=0,
        active_workers=0,
    )