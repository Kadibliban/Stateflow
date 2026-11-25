"""
StateFlow Workflow Service

Business logic for workflow management, versions, and steps.
"""
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.workflow import (
    Workflow,
    WorkflowVersion,
    WorkflowStep,
    RetryPolicy,
    WorkflowStatus,
    StepType,
)
from app.models.organization import OrganizationMember, MemberRole
from app.repositories.workflow_repository import (
    WorkflowRepository,
    WorkflowVersionRepository,
    WorkflowStepRepository,
    RetryPolicyRepository,
)
from app.repositories.organization_repository import OrganizationMemberRepository
from app.schemas.workflow import (
    WorkflowResponse,
    WorkflowVersionResponse,
    WorkflowStepResponse,
    RetryPolicyResponse,
    WorkflowDefinition,
)


class WorkflowService:
    """Service for workflow operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.workflow_repo = WorkflowRepository(session)
        self.version_repo = WorkflowVersionRepository(session)
        self.step_repo = WorkflowStepRepository(session)
        self.policy_repo = RetryPolicyRepository(session)
        self.member_repo = OrganizationMemberRepository(session)

    async def create_workflow(
        self,
        org_id: UUID,
        user_id: UUID,
        name: str,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[dict] = None,
    ) -> WorkflowResponse:
        """Create a new workflow."""
        if not await self.member_repo.has_role(org_id, user_id, [MemberRole.OWNER, MemberRole.ADMINISTRATOR, MemberRole.DEVELOPER]):
            raise ValueError("Insufficient permissions")

        if await self.workflow_repo.check_name_exists(org_id, name):
            raise ValueError("Workflow with this name already exists")

        workflow = Workflow(
            organization_id=org_id,
            name=name,
            description=description,
            tags=tags or [],
            metadata=metadata or {},
            created_by=user_id,
            status=WorkflowStatus.DRAFT,
        )
        workflow = await self.workflow_repo.create(workflow)
        await self.session.commit()

        return WorkflowResponse.model_validate(workflow)

    async def get_workflow(self, workflow_id: UUID, org_id: UUID, user_id: UUID) -> WorkflowResponse:
        """Get workflow by ID."""
        if not await self.member_repo.has_role(org_id, user_id, [MemberRole.OWNER, MemberRole.ADMINISTRATOR, MemberRole.DEVELOPER, MemberRole.VIEWER]):
            raise ValueError("Insufficient permissions")

        workflow = await self.workflow_repo.get_by_id_with_org(workflow_id, org_id)
        if not workflow:
            raise ValueError("Workflow not found")

        return WorkflowResponse.model_validate(workflow)

    async def list_workflows(
        self,
        org_id: UUID,
        user_id: UUID,
        skip: int = 0,
        limit: int = 20,
        status: Optional[WorkflowStatus] = None,
    ) -> List[WorkflowResponse]:
        """List workflows in organization."""
        if not await self.member_repo.has_role(org_id, user_id, [MemberRole.OWNER, MemberRole.ADMINISTRATOR, MemberRole.DEVELOPER, MemberRole.VIEWER]):
            raise ValueError("Insufficient permissions")

        workflows = await self.workflow_repo.list_workflows(org_id, skip, limit, status)
        return [WorkflowResponse.model_validate(w) for w in workflows]

    async def update_workflow(
        self,
        workflow_id: UUID,
        org_id: UUID,
        user_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[dict] = None,
    ) -> WorkflowResponse:
        """Update workflow (draft only)."""
        if not await self.member_repo.has_role(org_id, user_id, [MemberRole.OWNER, MemberRole.ADMINISTRATOR, MemberRole.DEVELOPER]):
            raise ValueError("Insufficient permissions")

        workflow = await self.workflow_repo.get_by_id_with_org(workflow_id, org_id)
        if not workflow:
            raise ValueError("Workflow not found")

        if workflow.status != WorkflowStatus.DRAFT:
            raise ValueError("Can only update draft workflows")

        if name is not None:
            if await self.workflow_repo.check_name_exists(org_id, name, exclude_id=workflow_id):
                raise ValueError("Workflow with this name already exists")
            workflow.name = name

        if description is not None:
            workflow.description = description
        if tags is not None:
            workflow.tags = tags
        if metadata is not None:
            workflow.metadata = metadata

        await self.workflow_repo.update(workflow)
        await self.session.commit()
        await self.session.refresh(workflow)

        return WorkflowResponse.model_validate(workflow)

    async def delete_workflow(self, workflow_id: UUID, org_id: UUID, user_id: UUID) -> None:
        """Delete workflow (not active)."""
        if not await self.member_repo.has_role(org_id, user_id, [MemberRole.OWNER, MemberRole.ADMINISTRATOR]):
            raise ValueError("Insufficient permissions")

        workflow = await self.workflow_repo.get_by_id_with_org(workflow_id, org_id)
        if not workflow:
            raise ValueError("Workflow not found")

        if workflow.status == WorkflowStatus.ACTIVE:
            raise ValueError("Cannot delete active workflow. Deactivate first.")

        await self.workflow_repo.delete(workflow_id)
        await self.session.commit()

    async def activate_workflow(
        self,
        workflow_id: UUID,
        org_id: UUID,
        user_id: UUID,
        changelog: Optional[str] = None,
    ) -> WorkflowResponse:
        """Activate workflow by creating a new version."""
        if not await self.member_repo.has_role(org_id, user_id, [MemberRole.OWNER, MemberRole.ADMINISTRATOR, MemberRole.DEVELOPER]):
            raise ValueError("Insufficient permissions")

        workflow = await self.workflow_repo.get_by_id_with_org(workflow_id, org_id)
        if not workflow:
            raise ValueError("Workflow not found")

        if workflow.status == WorkflowStatus.ACTIVE:
            raise ValueError("Workflow is already active")

        # Validate workflow has steps
        current_version = await self.version_repo.get_by_workflow_and_number(workflow_id, workflow.current_version)
        if not current_version:
            raise ValueError("Workflow version not found")

        steps = await self.step_repo.list_steps(current_version.id)
        if not steps:
            raise ValueError("Workflow must have at least one step")

        # Create new version
        new_version_num = workflow.current_version + 1
        version = WorkflowVersion(
            workflow_id=workflow_id,
            version_number=new_version_num,
            definition={},
            steps=[],
            connections=[],
            variables={},
            created_by=user_id,
            changelog=changelog,
        )
        await self.version_repo.create(version)
        await self.session.flush()

        workflow.current_version = new_version_num
        workflow.status = WorkflowStatus.ACTIVE
        workflow.activated_at = datetime.now(timezone.utc)

        await self.workflow_repo.update(workflow)
        await self.session.commit()
        await self.session.refresh(workflow)

        return WorkflowResponse.model_validate(workflow)

    async def deactivate_workflow(
        self,
        workflow_id: UUID,
        org_id: UUID,
        user_id: UUID,
    ) -> WorkflowResponse:
        """Deactivate workflow."""
        if not await self.member_repo.has_role(org_id, user_id, [MemberRole.OWNER, MemberRole.ADMINISTRATOR]):
            raise ValueError("Insufficient permissions")

        workflow = await self.workflow_repo.get_by_id_with_org(workflow_id, org_id)
        if not workflow:
            raise ValueError("Workflow not found")

        if workflow.status != WorkflowStatus.ACTIVE:
            raise ValueError("Workflow is not active")

        workflow.status = WorkflowStatus.DRAFT
        await self.workflow_repo.update(workflow)
        await self.session.commit()
        await self.session.refresh(workflow)

        return WorkflowResponse.model_validate(workflow)

    async def list_versions(
        self,
        workflow_id: UUID,
        org_id: UUID,
        user_id: UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> List[WorkflowVersionResponse]:
        """List workflow versions."""
        if not await self.member_repo.has_role(org_id, user_id, [MemberRole.OWNER, MemberRole.ADMINISTRATOR, MemberRole.DEVELOPER, MemberRole.VIEWER]):
            raise ValueError("Insufficient permissions")

        workflow = await self.workflow_repo.get_by_id_with_org(workflow_id, org_id)
        if not workflow:
            raise ValueError("Workflow not found")

        versions = await self.version_repo.list_versions(workflow_id, skip, limit)
        return [WorkflowVersionResponse.model_validate(v) for v in versions]

    async def get_version(
        self,
        workflow_id: UUID,
        version_number: int,
        org_id: UUID,
        user_id: UUID,
    ) -> WorkflowVersionResponse:
        """Get specific workflow version."""
        if not await self.member_repo.has_role(org_id, user_id, [MemberRole.OWNER, MemberRole.ADMINISTRATOR, MemberRole.DEVELOPER, MemberRole.VIEWER]):
            raise ValueError("Insufficient permissions")

        version = await self.version_repo.get_by_workflow_and_number(workflow_id, version_number)
        if not version:
            raise ValueError("Version not found")

        return WorkflowVersionResponse.model_validate(version)

    # Step management
    async def create_step(
        self,
        workflow_id: UUID,
        org_id: UUID,
        user_id: UUID,
        step_key: str,
        name: str,
        step_type: str,
        handler: str,
        version_number: Optional[int] = None,
        description: Optional[str] = None,
        config: Optional[dict] = None,
        input_mapping: Optional[dict] = None,
        output_mapping: Optional[dict] = None,
        timeout_seconds: int = 300,
        retry_policy_id: Optional[UUID] = None,
        compensation_handler: Optional[str] = None,
        compensation_config: Optional[dict] = None,
        depends_on: Optional[List[str]] = None,
        is_critical: bool = True,
        continue_on_failure: bool = False,
    ) -> WorkflowStepResponse:
        """Add step to workflow version."""
        if not await self.member_repo.has_role(org_id, user_id, [MemberRole.OWNER, MemberRole.ADMINISTRATOR, MemberRole.DEVELOPER]):
            raise ValueError("Insufficient permissions")

        workflow = await self.workflow_repo.get_by_id_with_org(workflow_id, org_id)
        if not workflow:
            raise ValueError("Workflow not found")

        version_num = version_number or workflow.current_version
        version = await self.version_repo.get_by_workflow_and_number(workflow_id, version_num)
        if not version:
            raise ValueError("Version not found")

        if workflow.status == WorkflowStatus.ACTIVE and version_num == workflow.current_version:
            raise ValueError("Cannot modify steps of active workflow version")

        if await self.step_repo.check_key_exists(version.id, step_key):
            raise ValueError("Step key already exists")

        if retry_policy_id:
            policy = await self.policy_repo.get_by_id(retry_policy_id)
            if not policy:
                raise ValueError("Retry policy not found")

        max_order = await self.step_repo.get_max_order(version.id)

        step = WorkflowStep(
            version_id=version.id,
            step_key=step_key,
            name=name,
            description=description,
            step_type=StepType(step_type),
            order=max_order + 1,
            handler=handler,
            config=config or {},
            input_mapping=input_mapping or {},
            output_mapping=output_mapping or {},
            timeout_seconds=timeout_seconds,
            retry_policy_id=retry_policy_id,
            compensation_handler=compensation_handler,
            compensation_config=compensation_config or {},
            depends_on=depends_on or [],
            is_critical=is_critical,
            continue_on_failure=continue_on_failure,
        )
        step = await self.step_repo.create(step)
        await self.session.commit()

        return WorkflowStepResponse.model_validate(step)

    async def list_steps(
        self,
        workflow_id: UUID,
        org_id: UUID,
        user_id: UUID,
        version_number: Optional[int] = None,
    ) -> List[WorkflowStepResponse]:
        """List workflow steps."""
        if not await self.member_repo.has_role(org_id, user_id, [MemberRole.OWNER, MemberRole.ADMINISTRATOR, MemberRole.DEVELOPER, MemberRole.VIEWER]):
            raise ValueError("Insufficient permissions")

        workflow = await self.workflow_repo.get_by_id_with_org(workflow_id, org_id)
        if not workflow:
            raise ValueError("Workflow not found")

        version_num = version_number or workflow.current_version
        version = await self.version_repo.get_by_workflow_and_number(workflow_id, version_num)
        if not version:
            raise ValueError("Version not found")

        steps = await self.step_repo.list_steps(version.id)
        return [WorkflowStepResponse.model_validate(s) for s in steps]

    async def get_workflow_definition(
        self,
        workflow_id: UUID,
        org_id: UUID,
        user_id: UUID,
        version_number: Optional[int] = None,
    ) -> WorkflowDefinition:
        """Get complete workflow definition for visual editor."""
        if not await self.member_repo.has_role(org_id, user_id, [MemberRole.OWNER, MemberRole.ADMINISTRATOR, MemberRole.DEVELOPER, MemberRole.VIEWER]):
            raise ValueError("Insufficient permissions")

        workflow = await self.workflow_repo.get_by_id_with_org(workflow_id, org_id)
        if not workflow:
            raise ValueError("Workflow not found")

        version_num = version_number or workflow.current_version
        version = await self.version_repo.get_by_workflow_and_number(workflow_id, version_num)
        if not version:
            raise ValueError("Version not found")

        steps = await self.step_repo.list_steps(version.id)
        policies = await self.policy_repo.list_policies()

        return WorkflowDefinition(
            workflow=WorkflowResponse.model_validate(workflow),
            version=WorkflowVersionResponse.model_validate(version),
            steps=[WorkflowStepResponse.model_validate(s) for s in steps],
            retry_policies=[RetryPolicyResponse.model_validate(p) for p in policies],
        )


class RetryPolicyService:
    """Service for retry policy operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.policy_repo = RetryPolicyRepository(session)
        self.member_repo = OrganizationMemberRepository(session)

    async def create_retry_policy(
        self,
        org_id: UUID,
        user_id: UUID,
        name: str,
        max_attempts: int = 3,
        base_delay_seconds: float = 1.0,
        max_delay_seconds: float = 60.0,
        exponential_base: float = 2.0,
        retryable_errors: Optional[List[str]] = None,
        non_retryable_errors: Optional[List[str]] = None,
    ) -> RetryPolicyResponse:
        """Create a retry policy."""
        if not await self.member_repo.has_role(org_id, user_id, [MemberRole.OWNER, MemberRole.ADMINISTRATOR, MemberRole.DEVELOPER]):
            raise ValueError("Insufficient permissions")

        existing = await self.policy_repo.get_by_name(name)
        if existing:
            raise ValueError("Retry policy with this name already exists")

        policy = RetryPolicy(
            name=name,
            max_attempts=max_attempts,
            base_delay_seconds=base_delay_seconds,
            max_delay_seconds=max_delay_seconds,
            exponential_base=exponential_base,
            retryable_errors=retryable_errors or [],
            non_retryable_errors=non_retryable_errors or [],
        )
        policy = await self.policy_repo.create(policy)
        await self.session.commit()

        return RetryPolicyResponse.model_validate(policy)

    async def list_retry_policies(self, org_id: UUID, user_id: UUID) -> List[RetryPolicyResponse]:
        """List retry policies."""
        if not await self.member_repo.has_role(org_id, user_id, [MemberRole.OWNER, MemberRole.ADMINISTRATOR, MemberRole.DEVELOPER, MemberRole.VIEWER]):
            raise ValueError("Insufficient permissions")

        policies = await self.policy_repo.list_policies()
        return [RetryPolicyResponse.model_validate(p) for p in policies]