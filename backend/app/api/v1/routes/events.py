"""
StateFlow Event Routes

Execution event queries and timeline.
"""
from typing import Annotated, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.execution import WorkflowExecution
from app.models.event import ExecutionEvent, EventType
from app.models.organization import OrganizationMember, MemberRole
from app.models.user import User
from app.schemas.event import (
    ExecutionEventResponse,
    EventTimelineResponse,
    EventSummary,
)
from app.api.v1.routes.auth import get_current_user

router = APIRouter(prefix="/executions", tags=["Events"])


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


@router.get("/{execution_id}/events", response_model=EventTimelineResponse)
async def get_execution_events(
    execution_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
    event_type: str | None = Query(None, description="Filter by event type"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> EventTimelineResponse:
    """Get event timeline for an execution."""
    await get_org_membership(org_id, current_user, session)

    execution = await session.get(WorkflowExecution, execution_id)
    if not execution or execution.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found",
        )

    query = select(ExecutionEvent).where(ExecutionEvent.execution_id == execution_id)

    if event_type:
        try:
            query = query.where(ExecutionEvent.event_type == EventType(event_type))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid event type",
            )

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await session.execute(count_query)
    total = total.scalar() or 0

    # Get events
    query = query.order_by(ExecutionEvent.created_at).offset(skip).limit(limit)
    events = await session.execute(query)
    events = events.scalars().all()

    return EventTimelineResponse(
        execution_id=execution_id,
        events=[ExecutionEventResponse.model_validate(e) for e in events],
        total=total,
    )


@router.get("/{execution_id}/events/summary", response_model=List[EventSummary])
async def get_execution_events_summary(
    execution_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
) -> List[EventSummary]:
    """Get event summary for an execution."""
    await get_org_membership(org_id, current_user, session)

    execution = await session.get(WorkflowExecution, execution_id)
    if not execution or execution.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found",
        )

    # Get event counts by type
    from sqlalchemy import func as sql_func
    query = (
        select(ExecutionEvent.event_type, sql_func.count(ExecutionEvent.id), sql_func.max(ExecutionEvent.created_at))
        .where(ExecutionEvent.execution_id == execution_id)
        .group_by(ExecutionEvent.event_type)
    )
    result = await session.execute(query)
    rows = result.all()

    return [
        EventSummary(
            event_type=row[0],
            count=row[1],
            last_occurrence=row[2],
        )
        for row in rows
    ]