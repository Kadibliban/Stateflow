"""
StateFlow Workflow Repository

Data access layer for workflows, versions, steps, and retry policies.
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, update, delete, func
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


class WorkflowRepository:
    """Repository for workflow operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, workflow: Workflow) -> Workflow:
        """Create a new workflow."""
        self.session.add(workflow)
        await self.session.flush()
        await self.session.refresh(workflow)
        return workflow

    async def get_by_id(self, workflow_id: UUID) -> Optional[Workflow]:
        """Get workflow by ID."""
        result = await self.session.execute(
            select(Workflow).where(Workflow.id == workflow_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_org(self, workflow_id: UUID, org_id: UUID) -> Optional[Workflow]:
        """Get workflow by ID and organization."""
        result = await self.session.execute(
            select(Workflow).where(Workflow.id == workflow_id, Workflow.organization_id == org_id)
        )
        return result.scalar_one_or_none()

    async def update(self, workflow: Workflow) -> Workflow:
        """Update workflow."""
        await self.session.flush()
        await self.session.refresh(workflow)
        return workflow

    async def delete(self, workflow_id: UUID) -> bool:
        """Delete workflow."""
        result = await self.session.execute(
            delete(Workflow).where(Workflow.id == workflow_id)
        )
        return result.rowcount > 0

    async def list_workflows(
        self,
        org_id: UUID,
        skip: int = 0,
        limit: int = 20,
        status: Optional[WorkflowStatus] = None,
    ) -> List[Workflow]:
        """List workflows in organization."""
        query = select(Workflow).where(
            Workflow.organization_id == org_id,
            Workflow.status != WorkflowStatus.ARCHIVED,
        )
        if status:
            query = query.where(Workflow.status == status)
        query = query.offset(skip).limit(limit).order_by(Workflow.updated_at.desc())
        result = await self.session.execute(query)
        return result.scalars().all()

    async def count_workflows(self, org_id: UUID, status: Optional[WorkflowStatus] = None) -> int:
        """Count workflows in organization."""
        query = select(func.count(Workflow.id)).where(
            Workflow.organization_id == org_id,
            Workflow.status != WorkflowStatus.ARCHIVED,
        )
        if status:
            query = query.where(Workflow.status == status)
        result = await self.session.execute(query)
        return result.scalar() or 0

    async def check_name_exists(self, org_id: UUID, name: str, exclude_id: Optional[UUID] = None) -> bool:
        """Check if workflow name exists in organization."""
        query = select(Workflow).where(
            Workflow.organization_id == org_id,
            Workflow.name == name,
        )
        if exclude_id:
            query = query.where(Workflow.id != exclude_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None


class WorkflowVersionRepository:
    """Repository for workflow version operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, version: WorkflowVersion) -> WorkflowVersion:
        """Create a new workflow version."""
        self.session.add(version)
        await self.session.flush()
        await self.session.refresh(version)
        return version

    async def get_by_id(self, version_id: UUID) -> Optional[WorkflowVersion]:
        """Get workflow version by ID."""
        result = await self.session.execute(
            select(WorkflowVersion).where(WorkflowVersion.id == version_id)
        )
        return result.scalar_one_or_none()

    async def get_by_workflow_and_number(
        self, workflow_id: UUID, version_number: int
    ) -> Optional[WorkflowVersion]:
        """Get workflow version by workflow ID and version number."""
        result = await self.session.execute(
            select(WorkflowVersion).where(
                WorkflowVersion.workflow_id == workflow_id,
                WorkflowVersion.version_number == version_number,
            )
        )
        return result.scalar_one_or_none()

    async def get_with_steps(self, version_id: UUID) -> Optional[WorkflowVersion]:
        """Get workflow version with steps loaded."""
        result = await self.session.execute(
            select(WorkflowVersion)
            .options(selectinload(WorkflowVersion.steps_def))
            .where(WorkflowVersion.id == version_id)
        )
        return result.scalar_one_or_none()

    async def list_versions(
        self,
        workflow_id: UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> List[WorkflowVersion]:
        """List workflow versions."""
        query = (
            select(WorkflowVersion)
            .where(WorkflowVersion.workflow_id == workflow_id)
            .order_by(WorkflowVersion.version_number.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_latest_version(self, workflow_id: UUID) -> Optional[WorkflowVersion]:
        """Get latest workflow version."""
        result = await self.session.execute(
            select(WorkflowVersion)
            .where(WorkflowVersion.workflow_id == workflow_id)
            .order_by(WorkflowVersion.version_number.desc())
        )
        return result.scalar_one_or_none()


class WorkflowStepRepository:
    """Repository for workflow step operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, step: WorkflowStep) -> WorkflowStep:
        """Create a new workflow step."""
        self.session.add(step)
        await self.session.flush()
        await self.session.refresh(step)
        return step

    async def get_by_id(self, step_id: UUID) -> Optional[WorkflowStep]:
        """Get workflow step by ID."""
        result = await self.session.execute(
            select(WorkflowStep).where(WorkflowStep.id == step_id)
        )
        return result.scalar_one_or_none()

    async def get_by_version_and_key(
        self, version_id: UUID, step_key: str
    ) -> Optional[WorkflowStep]:
        """Get workflow step by version and key."""
        result = await self.session.execute(
            select(WorkflowStep).where(
                WorkflowStep.version_id == version_id,
                WorkflowStep.step_key == step_key,
            )
        )
        return result.scalar_one_or_none()

    async def update(self, step: WorkflowStep) -> WorkflowStep:
        """Update workflow step."""
        await self.session.flush()
        await self.session.refresh(step)
        return step

    async def delete(self, step_id: UUID) -> bool:
        """Delete workflow step."""
        result = await self.session.execute(
            delete(WorkflowStep).where(WorkflowStep.id == step_id)
        )
        return result.rowcount > 0

    async def list_steps(
        self,
        version_id: UUID,
    ) -> List[WorkflowStep]:
        """List workflow steps ordered by order."""
        result = await self.session.execute(
            select(WorkflowStep)
            .where(WorkflowStep.version_id == version_id)
            .order_by(WorkflowStep.order)
        )
        return result.scalars().all()

    async def get_max_order(self, version_id: UUID) -> int:
        """Get maximum order value for steps in version."""
        result = await self.session.execute(
            select(func.max(WorkflowStep.order)).where(WorkflowStep.version_id == version_id)
        )
        return result.scalar() or 0

    async def check_key_exists(self, version_id: UUID, step_key: str, exclude_id: Optional[UUID] = None) -> bool:
        """Check if step key exists in version."""
        query = select(WorkflowStep).where(
            WorkflowStep.version_id == version_id,
            WorkflowStep.step_key == step_key,
        )
        if exclude_id:
            query = query.where(WorkflowStep.id != exclude_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None


class RetryPolicyRepository:
    """Repository for retry policy operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, policy: RetryPolicy) -> RetryPolicy:
        """Create a new retry policy."""
        self.session.add(policy)
        await self.session.flush()
        await self.session.refresh(policy)
        return policy

    async def get_by_id(self, policy_id: UUID) -> Optional[RetryPolicy]:
        """Get retry policy by ID."""
        result = await self.session.execute(
            select(RetryPolicy).where(RetryPolicy.id == policy_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Optional[RetryPolicy]:
        """Get retry policy by name."""
        result = await self.session.execute(
            select(RetryPolicy).where(RetryPolicy.name == name)
        )
        return result.scalar_one_or_none()

    async def list_policies(self) -> List[RetryPolicy]:
        """List all retry policies."""
        result = await self.session.execute(select(RetryPolicy).order_by(RetryPolicy.name))
        return result.scalars().all()