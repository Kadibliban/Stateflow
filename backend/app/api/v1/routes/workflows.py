"""
StateFlow Workflow Routes

Workflow CRUD, versioning, and step management.
"""
from datetime import datetime, timezone
from typing import Annotated, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_session
from app.models.workflow import (
    Workflow,
    WorkflowVersion,
    WorkflowStep,
    WorkflowStatus,
    StepType,
    RetryPolicy,
)
from app.models.organization import OrganizationMember, MemberRole
from app.models.user import User
from app.schemas.workflow import (
    WorkflowCreate,
    WorkflowUpdate,
    WorkflowResponse,
    WorkflowVersionResponse,
    WorkflowStepCreate,
    WorkflowStepUpdate,
    WorkflowStepResponse,
    RetryPolicyCreate,
    RetryPolicyResponse,
    WorkflowDefinition,
)
from app.api.v1.routes.auth import get_current_user
from app.services.workflow_validation import WorkflowValidationService

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


# Workflow CRUD
@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    request: WorkflowCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
) -> WorkflowResponse:
    """Create a new workflow."""
    # Check membership (developer or above)
    await get_org_membership(org_id, current_user, session, [MemberRole.OWNER, MemberRole.ADMINISTRATOR, MemberRole.DEVELOPER])

    # Check name uniqueness
    existing = await session.execute(
        select(Workflow).where(
            Workflow.organization_id == org_id,
            Workflow.name == request.name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Workflow with this name already exists",
        )

    workflow = Workflow(
        organization_id=org_id,
        name=request.name,
        description=request.description,
        tags=request.tags,
        workflow_metadata=request.workflow_metadata,
        created_by=current_user.id,
        status=WorkflowStatus.DRAFT,
    )
    session.add(workflow)
    await session.flush()

    # Create initial version for draft workflow
    version = WorkflowVersion(
        workflow_id=workflow.id,
        version_number=1,
        definition={},
        steps=[],
        connections=[],
        variables={},
        created_by=current_user.id,
        changelog="Initial version",
    )
    session.add(version)
    await session.commit()
    await session.refresh(workflow)

    return WorkflowResponse.model_validate(workflow)


@router.get("", response_model=List[WorkflowResponse])
async def list_workflows(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = Query(None, description="Filter by status"),
) -> List[WorkflowResponse]:
    """List workflows in organization."""
    # Check membership
    await get_org_membership(org_id, current_user, session)

    query = select(Workflow).where(
        Workflow.organization_id == org_id,
        Workflow.status != WorkflowStatus.ARCHIVED,
    )
    if status:
        query = query.where(Workflow.status == WorkflowStatus(status))

    query = query.offset(skip).limit(limit).order_by(Workflow.updated_at.desc())
    workflows = await session.execute(query)
    workflows = workflows.scalars().all()

    return [WorkflowResponse.model_validate(w) for w in workflows]


# Retry policies
@router.post("/retry-policies", response_model=RetryPolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_retry_policy(
    request: RetryPolicyCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
) -> RetryPolicyResponse:
    """Create retry policy."""
    await get_org_membership(org_id, current_user, session, [MemberRole.OWNER, MemberRole.ADMINISTRATOR, MemberRole.DEVELOPER])

    existing = await session.execute(
        select(RetryPolicy).where(RetryPolicy.name == request.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Retry policy with this name already exists",
        )

    policy = RetryPolicy(
        name=request.name,
        max_attempts=request.max_attempts,
        base_delay_seconds=request.base_delay_seconds,
        max_delay_seconds=request.max_delay_seconds,
        exponential_base=request.exponential_base,
        retryable_errors=request.retryable_errors,
        non_retryable_errors=request.non_retryable_errors,
    )
    session.add(policy)
    await session.commit()
    await session.refresh(policy)

    return RetryPolicyResponse.model_validate(policy)


@router.get("/retry-policies", response_model=List[RetryPolicyResponse])
async def list_retry_policies(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
) -> List[RetryPolicyResponse]:
    """List retry policies."""
    await get_org_membership(org_id, current_user, session)

    policies = await session.execute(
        select(RetryPolicy).order_by(RetryPolicy.name)
    )
    policies = policies.scalars().all()

    return [RetryPolicyResponse.model_validate(p) for p in policies]


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
) -> WorkflowResponse:
    """Get workflow by ID."""
    await get_org_membership(org_id, current_user, session)

    workflow = await session.get(Workflow, workflow_id)
    if not workflow or workflow.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    return WorkflowResponse.model_validate(workflow)


@router.post("/{workflow_id}/clone", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def clone_workflow(
    workflow_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
    name: str = Query(..., description="Name for the cloned workflow"),
    version_number: int | None = Query(None, description="Version to clone (defaults to current)"),
) -> WorkflowResponse:
    """Clone a workflow with all its steps."""
    await get_org_membership(org_id, current_user, session, [MemberRole.OWNER, MemberRole.ADMINISTRATOR, MemberRole.DEVELOPER])

    # Check name uniqueness
    existing = await session.execute(
        select(Workflow).where(
            Workflow.organization_id == org_id,
            Workflow.name == name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Workflow with this name already exists",
        )

    # Get source workflow
    source_workflow = await session.get(Workflow, workflow_id)
    if not source_workflow or source_workflow.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    version_num = version_number or source_workflow.current_version
    source_version = await session.execute(
        select(WorkflowVersion).where(
            WorkflowVersion.workflow_id == workflow_id,
            WorkflowVersion.version_number == version_num,
        )
        .options(selectinload(WorkflowVersion.steps_def))
    )
    source_version = source_version.scalar_one_or_none()
    if not source_version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source workflow version not found",
        )

    # Create new workflow
    new_workflow = Workflow(
        organization_id=org_id,
        name=name,
        description=source_workflow.description,
        tags=source_workflow.tags,
        workflow_metadata=source_workflow.workflow_metadata,
        created_by=current_user.id,
        status=WorkflowStatus.DRAFT,
    )
    session.add(new_workflow)
    await session.flush()

    # Create version 1 for new workflow
    new_version = WorkflowVersion(
        workflow_id=new_workflow.id,
        version_number=1,
        definition=source_version.definition,
        steps=source_version.steps,
        connections=source_version.connections,
        variables=source_version.variables,
        created_by=current_user.id,
        changelog=f"Cloned from workflow {source_workflow.name} v{version_num}",
    )
    session.add(new_version)
    await session.flush()

    # Clone steps
    for source_step in source_version.steps_def:
        new_step = WorkflowStep(
            version_id=new_version.id,
            step_key=source_step.step_key,
            name=source_step.name,
            description=source_step.description,
            step_type=source_step.step_type,
            order=source_step.order,
            handler=source_step.handler,
            config=source_step.config,
            input_mapping=source_step.input_mapping,
            output_mapping=source_step.output_mapping,
            timeout_seconds=source_step.timeout_seconds,
            retry_policy_id=source_step.retry_policy_id,
            compensation_handler=source_step.compensation_handler,
            compensation_config=source_step.compensation_config,
            depends_on=source_step.depends_on,
            is_critical=source_step.is_critical,
            continue_on_failure=source_step.continue_on_failure,
        )
        session.add(new_step)

    new_workflow.current_version = 1
    await session.commit()
    await session.refresh(new_workflow)

    return WorkflowResponse.model_validate(new_workflow)


@router.patch("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: UUID,
    request: WorkflowUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
) -> WorkflowResponse:
    """Update workflow."""
    await get_org_membership(org_id, current_user, session, [MemberRole.OWNER, MemberRole.ADMINISTRATOR, MemberRole.DEVELOPER])

    workflow = await session.get(Workflow, workflow_id)
    if not workflow or workflow.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    if workflow.status != WorkflowStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only update draft workflows",
        )

    if request.name is not None:
        # Check name uniqueness
        existing = await session.execute(
            select(Workflow).where(
                Workflow.organization_id == org_id,
                Workflow.name == request.name,
                Workflow.id != workflow_id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Workflow with this name already exists",
            )
        workflow.name = request.name

    if request.description is not None:
        workflow.description = request.description
    if request.tags is not None:
        workflow.tags = request.tags
    if request.workflow_metadata is not None:
        workflow.workflow_metadata = request.workflow_metadata

    await session.commit()
    await session.refresh(workflow)

    return WorkflowResponse.model_validate(workflow)


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
) -> None:
    """Delete workflow."""
    await get_org_membership(org_id, current_user, session, [MemberRole.OWNER, MemberRole.ADMINISTRATOR])

    workflow = await session.get(Workflow, workflow_id)
    if not workflow or workflow.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    if workflow.status == WorkflowStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete active workflow. Deactivate first.",
        )

    await session.delete(workflow)
    await session.commit()


# Workflow activation/deactivation
@router.post("/{workflow_id}/activate", response_model=WorkflowResponse)
async def activate_workflow(
    workflow_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
    changelog: str | None = Query(None, description="Version changelog"),
) -> WorkflowResponse:
    """Activate workflow (create new version)."""
    await get_org_membership(org_id, current_user, session, [MemberRole.OWNER, MemberRole.ADMINISTRATOR, MemberRole.DEVELOPER])

    workflow = await session.get(Workflow, workflow_id)
    if not workflow or workflow.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    if workflow.status == WorkflowStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workflow is already active",
        )

    # Validate workflow definition before activation
    validation_service = WorkflowValidationService(session)
    validation_result = await validation_service.validate_workflow_for_activation(workflow_id)
    if not validation_result["valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Workflow validation failed: {'; '.join(validation_result['errors'])}",
        )

    # Get steps from current version to copy
    old_version = await session.execute(
        select(WorkflowVersion).where(
            WorkflowVersion.workflow_id == workflow_id,
            WorkflowVersion.version_number == workflow.current_version,
        )
    )
    old_version = old_version.scalar_one_or_none()

    old_steps = []
    if old_version:
        old_steps_result = await session.execute(
            select(WorkflowStep).where(WorkflowStep.version_id == old_version.id).order_by(WorkflowStep.order)
        )
        old_steps = old_steps_result.scalars().all()

    # Create new version
    new_version = workflow.current_version + 1
    version = WorkflowVersion(
        workflow_id=workflow_id,
        version_number=new_version,
        definition={},
        steps=[],
        connections=[],
        variables={},
        created_by=current_user.id,
        changelog=changelog,
    )
    session.add(version)
    await session.flush()

    # Copy steps to new version
    for old_step in old_steps:
        new_step = WorkflowStep(
            version_id=version.id,
            step_key=old_step.step_key,
            name=old_step.name,
            description=old_step.description,
            step_type=old_step.step_type,
            order=old_step.order,
            handler=old_step.handler,
            config=old_step.config,
            input_mapping=old_step.input_mapping,
            output_mapping=old_step.output_mapping,
            timeout_seconds=old_step.timeout_seconds,
            retry_policy_id=old_step.retry_policy_id,
            compensation_handler=old_step.compensation_handler,
            compensation_config=old_step.compensation_config,
            depends_on=old_step.depends_on,
            is_critical=old_step.is_critical,
            continue_on_failure=old_step.continue_on_failure,
        )
        session.add(new_step)

    workflow.current_version = new_version
    workflow.status = WorkflowStatus.ACTIVE
    from datetime import datetime, timezone
    workflow.activated_at = datetime.now(timezone.utc)

    await session.commit()
    await session.refresh(workflow)

    return WorkflowResponse.model_validate(workflow)


@router.post("/{workflow_id}/deactivate", response_model=WorkflowResponse)
async def deactivate_workflow(
    workflow_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
) -> WorkflowResponse:
    """Deactivate workflow."""
    await get_org_membership(org_id, current_user, session, [MemberRole.OWNER, MemberRole.ADMINISTRATOR])

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

    workflow.status = WorkflowStatus.DRAFT
    await session.commit()
    await session.refresh(workflow)

    return WorkflowResponse.model_validate(workflow)


# Workflow versions
@router.get("/{workflow_id}/versions", response_model=List[WorkflowVersionResponse])
async def list_versions(
    workflow_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> List[WorkflowVersionResponse]:
    """List workflow versions."""
    await get_org_membership(org_id, current_user, session)

    workflow = await session.get(Workflow, workflow_id)
    if not workflow or workflow.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    versions = await session.execute(
        select(WorkflowVersion)
        .where(WorkflowVersion.workflow_id == workflow_id)
        .order_by(WorkflowVersion.version_number.desc())
        .offset(skip)
        .limit(limit)
    )
    versions = versions.scalars().all()

    return [WorkflowVersionResponse.model_validate(v) for v in versions]


@router.get("/{workflow_id}/versions/{version_number}", response_model=WorkflowVersionResponse)
async def get_version(
    workflow_id: UUID,
    version_number: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
) -> WorkflowVersionResponse:
    """Get specific workflow version."""
    await get_org_membership(org_id, current_user, session)

    version = await session.execute(
        select(WorkflowVersion)
        .where(
            WorkflowVersion.workflow_id == workflow_id,
            WorkflowVersion.version_number == version_number,
        )
        .options(selectinload(WorkflowVersion.steps_def))
    )
    version = version.scalar_one_or_none()

    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version not found",
        )

    return WorkflowVersionResponse.model_validate(version)


# Workflow steps
@router.post("/{workflow_id}/steps", response_model=WorkflowStepResponse, status_code=status.HTTP_201_CREATED)
async def create_step(
    workflow_id: UUID,
    request: WorkflowStepCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
    version_number: int | None = Query(None, description="Version number (defaults to current)"),
) -> WorkflowStepResponse:
    """Add step to workflow version."""
    await get_org_membership(org_id, current_user, session, [MemberRole.OWNER, MemberRole.ADMINISTRATOR, MemberRole.DEVELOPER])

    workflow = await session.get(Workflow, workflow_id)
    if not workflow or workflow.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    version_num = version_number or workflow.current_version
    version = await session.execute(
        select(WorkflowVersion).where(
            WorkflowVersion.workflow_id == workflow_id,
            WorkflowVersion.version_number == version_num,
        )
    )
    version = version.scalar_one_or_none()
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version not found",
        )

    if workflow.status == WorkflowStatus.ACTIVE and version_num == workflow.current_version:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify steps of active workflow version",
        )

    # Check step_key uniqueness
    existing = await session.execute(
        select(WorkflowStep).where(
            WorkflowStep.version_id == version.id,
            WorkflowStep.step_key == request.step_key,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Step key already exists",
        )

    # Validate retry policy if provided
    if request.retry_policy_id:
        policy = await session.get(RetryPolicy, request.retry_policy_id)
        if not policy:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Retry policy not found",
            )

    # Determine order
    max_order = await session.execute(
        select(func.max(WorkflowStep.order)).where(WorkflowStep.version_id == version.id)
    )
    max_order = max_order.scalar() or 0

    step = WorkflowStep(
        version_id=version.id,
        step_key=request.step_key,
        name=request.name,
        description=request.description,
        step_type=StepType(request.step_type),
        order=request.order if request.order is not None else max_order + 1,
        handler=request.handler,
        config=request.config,
        input_mapping=request.input_mapping,
        output_mapping=request.output_mapping,
        timeout_seconds=request.timeout_seconds,
        retry_policy_id=request.retry_policy_id,
        compensation_handler=request.compensation_handler,
        compensation_config=request.compensation_config,
        depends_on=request.depends_on,
        is_critical=request.is_critical,
        continue_on_failure=request.continue_on_failure,
    )
    session.add(step)
    await session.commit()
    await session.refresh(step)

    return WorkflowStepResponse.model_validate(step)


@router.get("/{workflow_id}/steps", response_model=List[WorkflowStepResponse])
async def list_steps(
    workflow_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
    version_number: int | None = Query(None, description="Version number"),
) -> List[WorkflowStepResponse]:
    """List workflow steps."""
    await get_org_membership(org_id, current_user, session)

    workflow = await session.get(Workflow, workflow_id)
    if not workflow or workflow.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    version_num = version_number or workflow.current_version
    version = await session.execute(
        select(WorkflowVersion).where(
            WorkflowVersion.workflow_id == workflow_id,
            WorkflowVersion.version_number == version_num,
        )
    )
    version = version.scalar_one_or_none()
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version not found",
        )

    steps = await session.execute(
        select(WorkflowStep)
        .where(WorkflowStep.version_id == version.id)
        .order_by(WorkflowStep.order)
    )
    steps = steps.scalars().all()

    return [WorkflowStepResponse.model_validate(s) for s in steps]


@router.patch("/{workflow_id}/steps/{step_key}", response_model=WorkflowStepResponse)
async def update_step(
    workflow_id: UUID,
    step_key: str,
    request: WorkflowStepUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
    version_number: int | None = Query(None, description="Version number"),
) -> WorkflowStepResponse:
    """Update a workflow step."""
    await get_org_membership(org_id, current_user, session, [MemberRole.OWNER, MemberRole.ADMINISTRATOR, MemberRole.DEVELOPER])

    workflow = await session.get(Workflow, workflow_id)
    if not workflow or workflow.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    version_num = version_number or workflow.current_version
    version = await session.execute(
        select(WorkflowVersion).where(
            WorkflowVersion.workflow_id == workflow_id,
            WorkflowVersion.version_number == version_num,
        )
    )
    version = version.scalar_one_or_none()
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version not found",
        )

    if workflow.status == WorkflowStatus.ACTIVE and version_num == workflow.current_version:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify steps of active workflow version",
        )

    step = await session.execute(
        select(WorkflowStep).where(
            WorkflowStep.version_id == version.id,
            WorkflowStep.step_key == step_key,
        )
    )
    step = step.scalar_one_or_none()
    if not step:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Step not found",
        )

    # Validate retry policy if provided
    if request.retry_policy_id:
        policy = await session.get(RetryPolicy, request.retry_policy_id)
        if not policy:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Retry policy not found",
            )

    # Update fields
    if request.name is not None:
        step.name = request.name
    if request.description is not None:
        step.description = request.description
    if request.order is not None:
        # Check order uniqueness
        existing = await session.execute(
            select(WorkflowStep).where(
                WorkflowStep.version_id == version.id,
                WorkflowStep.order == request.order,
                WorkflowStep.step_key != step_key,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Step order already exists",
            )
        step.order = request.order
    if request.handler is not None:
        step.handler = request.handler
    if request.config is not None:
        step.config = request.config
    if request.input_mapping is not None:
        step.input_mapping = request.input_mapping
    if request.output_mapping is not None:
        step.output_mapping = request.output_mapping
    if request.timeout_seconds is not None:
        step.timeout_seconds = request.timeout_seconds
    if request.retry_policy_id is not None:
        step.retry_policy_id = request.retry_policy_id
    if request.compensation_handler is not None:
        step.compensation_handler = request.compensation_handler
    if request.compensation_config is not None:
        step.compensation_config = request.compensation_config
    if request.depends_on is not None:
        step.depends_on = request.depends_on
    if request.is_critical is not None:
        step.is_critical = request.is_critical
    if request.continue_on_failure is not None:
        step.continue_on_failure = request.continue_on_failure

    await session.commit()
    await session.refresh(step)

    return WorkflowStepResponse.model_validate(step)


@router.delete("/{workflow_id}/steps/{step_key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_step(
    workflow_id: UUID,
    step_key: str,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
    version_number: int | None = Query(None, description="Version number"),
) -> None:
    """Delete a workflow step."""
    await get_org_membership(org_id, current_user, session, [MemberRole.OWNER, MemberRole.ADMINISTRATOR, MemberRole.DEVELOPER])

    workflow = await session.get(Workflow, workflow_id)
    if not workflow or workflow.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    version_num = version_number or workflow.current_version
    version = await session.execute(
        select(WorkflowVersion).where(
            WorkflowVersion.workflow_id == workflow_id,
            WorkflowVersion.version_number == version_num,
        )
    )
    version = version.scalar_one_or_none()
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version not found",
        )

    if workflow.status == WorkflowStatus.ACTIVE and version_num == workflow.current_version:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete steps from active workflow version",
        )

    step = await session.execute(
        select(WorkflowStep).where(
            WorkflowStep.version_id == version.id,
            WorkflowStep.step_key == step_key,
        )
    )
    step = step.scalar_one_or_none()
    if not step:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Step not found",
        )

    # Check if other steps depend on this step
    other_steps = await session.execute(
        select(WorkflowStep).where(
            WorkflowStep.version_id == version.id,
            WorkflowStep.step_key != step_key,
        )
    )
    for other_step in other_steps.scalars().all():
        if step_key in (other_step.depends_on or []):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Step {other_step.step_key} depends on this step. Remove dependency first.",
            )

    await session.delete(step)
    await session.commit()


# Complete workflow definition for visual editor
@router.get("/{workflow_id}/definition", response_model=WorkflowDefinition)
async def get_workflow_definition(
    workflow_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
    version_number: int | None = Query(None, description="Version number"),
) -> WorkflowDefinition:
    """Get complete workflow definition for visual editor."""
    await get_org_membership(org_id, current_user, session)

    workflow = await session.get(Workflow, workflow_id)
    if not workflow or workflow.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    version_num = version_number or workflow.current_version
    version = await session.execute(
        select(WorkflowVersion)
        .where(
            WorkflowVersion.workflow_id == workflow_id,
            WorkflowVersion.version_number == version_num,
        )
        .options(selectinload(WorkflowVersion.steps_def))
    )
    version = version.scalar_one_or_none()
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version not found",
        )

    steps = await session.execute(
        select(WorkflowStep)
        .where(WorkflowStep.version_id == version.id)
        .order_by(WorkflowStep.order)
    )
    steps = steps.scalars().all()

    policies = await session.execute(select(RetryPolicy))
    policies = policies.scalars().all()

    return WorkflowDefinition(
        workflow=WorkflowResponse.model_validate(workflow),
        version=WorkflowVersionResponse.model_validate(version),
        steps=[WorkflowStepResponse.model_validate(s) for s in steps],
        retry_policies=[RetryPolicyResponse.model_validate(p) for p in policies],
    )


# Workflow validation
@router.post("/{workflow_id}/validate", status_code=status.HTTP_200_OK)
async def validate_workflow(
    workflow_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
    version_number: int | None = Query(None, description="Version number (defaults to current)"),
) -> dict:
    """Validate workflow definition for activation."""
    await get_org_membership(org_id, current_user, session, [MemberRole.OWNER, MemberRole.ADMINISTRATOR, MemberRole.DEVELOPER, MemberRole.VIEWER])

    validation_service = WorkflowValidationService(session)
    result = await validation_service.validate_workflow_for_activation(workflow_id, version_number)

    return result


# Workflow export/import
@router.get("/{workflow_id}/export", status_code=status.HTTP_200_OK)
async def export_workflow(
    workflow_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
    version_number: int | None = Query(None, description="Version number (defaults to current)"),
) -> dict:
    """Export workflow definition as JSON for backup/import."""
    await get_org_membership(org_id, current_user, session, [MemberRole.OWNER, MemberRole.ADMINISTRATOR, MemberRole.DEVELOPER, MemberRole.VIEWER])

    workflow = await session.get(Workflow, workflow_id)
    if not workflow or workflow.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    version_num = version_number or workflow.current_version
    version = await session.execute(
        select(WorkflowVersion)
        .where(
            WorkflowVersion.workflow_id == workflow_id,
            WorkflowVersion.version_number == version_num,
        )
        .options(selectinload(WorkflowVersion.steps_def))
    )
    version = version.scalar_one_or_none()
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version not found",
        )

    steps = await session.execute(
        select(WorkflowStep)
        .where(WorkflowStep.version_id == version.id)
        .order_by(WorkflowStep.order)
    )
    steps = steps.scalars().all()

    # Get retry policies used by steps
    policy_ids = set(s.retry_policy_id for s in steps if s.retry_policy_id)
    policies = []
    if policy_ids:
        policies_result = await session.execute(
            select(RetryPolicy).where(RetryPolicy.id.in_(policy_ids))
        )
        policies = policies_result.scalars().all()

    export_data = {
        "workflow": {
            "name": workflow.name,
            "description": workflow.description,
            "tags": workflow.tags,
            "workflow_metadata": workflow.workflow_metadata,
        },
        "version": {
            "version_number": version.version_number,
            "definition": version.definition,
            "steps": version.steps,
            "connections": version.connections,
            "variables": version.variables,
            "changelog": version.changelog,
        },
        "steps": [
            {
                "step_key": s.step_key,
                "name": s.name,
                "description": s.description,
                "step_type": s.step_type.value if hasattr(s.step_type, 'value') else str(s.step_type),
                "order": s.order,
                "handler": s.handler,
                "config": s.config,
                "input_mapping": s.input_mapping,
                "output_mapping": s.output_mapping,
                "timeout_seconds": s.timeout_seconds,
                "retry_policy_name": None,  # Will be populated below
                "compensation_handler": s.compensation_handler,
                "compensation_config": s.compensation_config,
                "depends_on": s.depends_on,
                "is_critical": s.is_critical,
                "continue_on_failure": s.continue_on_failure,
            }
            for s in steps
        ],
        "retry_policies": [
            {
                "name": p.name,
                "max_attempts": p.max_attempts,
                "base_delay_seconds": p.base_delay_seconds,
                "max_delay_seconds": p.max_delay_seconds,
                "exponential_base": p.exponential_base,
                "retryable_errors": p.retryable_errors,
                "non_retryable_errors": p.non_retryable_errors,
            }
            for p in policies
        ],
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "exported_by": str(current_user.id),
    }

    # Add retry policy names to steps
    policy_map = {p.id: p.name for p in policies}
    for i, s in enumerate(steps):
        if s.retry_policy_id and s.retry_policy_id in policy_map:
            export_data["steps"][i]["retry_policy_name"] = policy_map[s.retry_policy_id]

    return export_data


@router.post("/import", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def import_workflow(
    request: dict,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    org_id: UUID = Query(..., description="Organization ID"),
    name: str | None = Query(None, description="New name for imported workflow (optional)"),
) -> WorkflowResponse:
    """Import workflow definition from JSON export."""
    await get_org_membership(org_id, current_user, session, [MemberRole.OWNER, MemberRole.ADMINISTRATOR, MemberRole.DEVELOPER])

    # Validate required fields
    if "workflow" not in request or "steps" not in request:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid export format: missing 'workflow' or 'steps'",
        )

    workflow_data = request["workflow"]
    workflow_name = name or workflow_data.get("name")
    if not workflow_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workflow name is required",
        )

    # Check name uniqueness
    existing = await session.execute(
        select(Workflow).where(
            Workflow.organization_id == org_id,
            Workflow.name == workflow_name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Workflow with this name already exists",
        )

    # Create workflow
    new_workflow = Workflow(
        organization_id=org_id,
        name=workflow_name,
        description=workflow_data.get("description"),
        tags=workflow_data.get("tags", []),
        workflow_metadata=workflow_data.get("workflow_metadata", {}),
        created_by=current_user.id,
        status=WorkflowStatus.DRAFT,
    )
    session.add(new_workflow)
    await session.flush()

    # Create version
    version_data = request.get("version", {})
    new_version = WorkflowVersion(
        workflow_id=new_workflow.id,
        version_number=1,
        definition=version_data.get("definition", {}),
        steps=version_data.get("steps", []),
        connections=version_data.get("connections", []),
        variables=version_data.get("variables", {}),
        created_by=current_user.id,
        changelog=version_data.get("changelog", "Imported workflow"),
    )
    session.add(new_version)
    await session.flush()

    # Create retry policies first
    policy_map = {}
    for policy_data in request.get("retry_policies", []):
        # Check if policy already exists
        existing_policy = await session.execute(
            select(RetryPolicy).where(RetryPolicy.name == policy_data["name"])
        )
        existing_policy = existing_policy.scalar_one_or_none()
        if existing_policy:
            policy_map[policy_data["name"]] = existing_policy.id
        else:
            policy = RetryPolicy(
                name=policy_data["name"],
                max_attempts=policy_data.get("max_attempts", 3),
                base_delay_seconds=policy_data.get("base_delay_seconds", 1.0),
                max_delay_seconds=policy_data.get("max_delay_seconds", 60.0),
                exponential_base=policy_data.get("exponential_base", 2.0),
                retryable_errors=policy_data.get("retryable_errors", []),
                non_retryable_errors=policy_data.get("non_retryable_errors", []),
            )
            session.add(policy)
            await session.flush()
            policy_map[policy_data["name"]] = policy.id

    # Create steps
    for step_data in request["steps"]:
        retry_policy_id = None
        if step_data.get("retry_policy_name") and step_data["retry_policy_name"] in policy_map:
            retry_policy_id = policy_map[step_data["retry_policy_name"]]

        step = WorkflowStep(
            version_id=new_version.id,
            step_key=step_data["step_key"],
            name=step_data["name"],
            description=step_data.get("description"),
            step_type=StepType(step_data.get("step_type", "action")),
            order=step_data.get("order", 0),
            handler=step_data["handler"],
            config=step_data.get("config", {}),
            input_mapping=step_data.get("input_mapping", {}),
            output_mapping=step_data.get("output_mapping", {}),
            timeout_seconds=step_data.get("timeout_seconds", 300),
            retry_policy_id=retry_policy_id,
            compensation_handler=step_data.get("compensation_handler"),
            compensation_config=step_data.get("compensation_config", {}),
            depends_on=step_data.get("depends_on", []),
            is_critical=step_data.get("is_critical", True),
            continue_on_failure=step_data.get("continue_on_failure", False),
        )
        session.add(step)

    new_workflow.current_version = 1
    await session.commit()
    await session.refresh(new_workflow)

    return WorkflowResponse.model_validate(new_workflow)