"""
StateFlow Worker Routes

Worker monitoring and health checks.
"""
from typing import Annotated, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.worker import WorkerHeartbeat
from app.models.organization import OrganizationMember, MemberRole
from app.models.user import User
from app.schemas.worker import (
    WorkerHeartbeatResponse,
    WorkerHealthResponse,
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


@router.get("", response_model=List[WorkerHeartbeatResponse])
async def list_workers(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
    status: str | None = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> List[WorkerHeartbeatResponse]:
    """List all workers."""
    await get_org_membership(org_id, current_user, session)

    query = select(WorkerHeartbeat)

    if status:
        query = query.where(WorkerHeartbeat.status == status)

    query = query.order_by(WorkerHeartbeat.last_heartbeat_at.desc()).offset(skip).limit(limit)
    workers = await session.execute(query)
    workers = workers.scalars().all()

    return [WorkerHeartbeatResponse.model_validate(w) for w in workers]


@router.get("/{worker_id}", response_model=WorkerHeartbeatResponse)
async def get_worker(
    worker_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
) -> WorkerHeartbeatResponse:
    """Get worker by ID."""
    await get_org_membership(org_id, current_user, session)

    worker = await session.execute(
        select(WorkerHeartbeat).where(WorkerHeartbeat.worker_id == worker_id)
    )
    worker = worker.scalar_one_or_none()

    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Worker not found",
        )

    return WorkerHeartbeatResponse.model_validate(worker)


@router.get("/health/summary", response_model=WorkerHealthResponse)
async def get_worker_health(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
) -> WorkerHealthResponse:
    """Get worker health summary."""
    await get_org_membership(org_id, current_user, session)

    from datetime import datetime, timezone, timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)

    # Total workers
    total = await session.execute(select(func.count(WorkerHeartbeat.id)))
    total = total.scalar() or 0

    # Healthy workers (heartbeat within last 5 minutes)
    healthy = await session.execute(
        select(func.count(WorkerHeartbeat.id)).where(
            WorkerHeartbeat.last_heartbeat_at >= cutoff,
            WorkerHeartbeat.status == "healthy",
        )
    )
    healthy = healthy.scalar() or 0

    # Unhealthy workers
    unhealthy = await session.execute(
        select(func.count(WorkerHeartbeat.id)).where(
            (WorkerHeartbeat.last_heartbeat_at < cutoff) | (WorkerHeartbeat.status != "healthy"),
        )
    )
    unhealthy = unhealthy.scalar() or 0

    # Capacity
    capacity_result = await session.execute(
        select(func.sum(WorkerHeartbeat.max_concurrency))
    )
    total_capacity = capacity_result.scalar() or 0

    load_result = await session.execute(
        select(func.sum(WorkerHeartbeat.current_executions))
    )
    current_load = load_result.scalar() or 0

    # Get all workers
    workers = await session.execute(
        select(WorkerHeartbeat).order_by(WorkerHeartbeat.last_heartbeat_at.desc())
    )
    workers = workers.scalars().all()

    return WorkerHealthResponse(
        total_workers=total,
        healthy_workers=healthy,
        unhealthy_workers=unhealthy,
        total_capacity=total_capacity,
        current_load=current_load,
        workers=[WorkerHeartbeatResponse.model_validate(w) for w in workers],
    )