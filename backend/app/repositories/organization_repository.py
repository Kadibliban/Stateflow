"""
StateFlow Organization Repository

Data access layer for organizations and memberships.
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.organization import Organization, OrganizationMember, MemberRole, OrganizationStatus
from app.models.user import User, Role


class OrganizationRepository:
    """Repository for organization operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, org: Organization) -> Organization:
        """Create a new organization."""
        self.session.add(org)
        await self.session.flush()
        await self.session.refresh(org)
        return org

    async def get_by_id(self, org_id: UUID) -> Optional[Organization]:
        """Get organization by ID."""
        result = await self.session.execute(
            select(Organization).where(Organization.id == org_id)
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Optional[Organization]:
        """Get organization by slug."""
        result = await self.session.execute(
            select(Organization).where(Organization.slug == slug)
        )
        return result.scalar_one_or_none()

    async def update(self, org: Organization) -> Organization:
        """Update organization."""
        await self.session.flush()
        await self.session.refresh(org)
        return org

    async def delete(self, org_id: UUID) -> bool:
        """Soft delete organization."""
        from datetime import datetime, timezone
        result = await self.session.execute(
            update(Organization)
            .where(Organization.id == org_id)
            .values(status=OrganizationStatus.DELETED, deleted_at=datetime.now(timezone.utc))
        )
        return result.rowcount > 0

    async def list_organizations(
        self,
        skip: int = 0,
        limit: int = 20,
        status: Optional[OrganizationStatus] = None,
    ) -> List[Organization]:
        """List organizations with pagination."""
        query = select(Organization)
        if status:
            query = query.where(Organization.status == status)
        else:
            query = query.where(Organization.status != OrganizationStatus.DELETED)
        query = query.offset(skip).limit(limit).order_by(Organization.created_at.desc())
        result = await self.session.execute(query)
        return result.scalars().all()

    async def count_organizations(self, status: Optional[OrganizationStatus] = None) -> int:
        """Count organizations."""
        query = select(func.count(Organization.id))
        if status:
            query = query.where(Organization.status == status)
        else:
            query = query.where(Organization.status != OrganizationStatus.DELETED)
        result = await self.session.execute(query)
        return result.scalar() or 0


class OrganizationMemberRepository:
    """Repository for organization membership operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, member: OrganizationMember) -> OrganizationMember:
        """Create a new membership."""
        self.session.add(member)
        await self.session.flush()
        await self.session.refresh(member)
        return member

    async def get_by_id(self, member_id: UUID) -> Optional[OrganizationMember]:
        """Get membership by ID."""
        result = await self.session.execute(
            select(OrganizationMember)
            .options(selectinload(OrganizationMember.user), selectinload(OrganizationMember.role))
            .where(OrganizationMember.id == member_id)
        )
        return result.scalar_one_or_none()

    async def get_by_org_and_user(self, org_id: UUID, user_id: UUID) -> Optional[OrganizationMember]:
        """Get membership by organization and user."""
        result = await self.session.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_active_by_org_and_user(self, org_id: UUID, user_id: UUID) -> Optional[OrganizationMember]:
        """Get active membership by organization and user."""
        result = await self.session.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == user_id,
                OrganizationMember.is_active == True,
            )
        )
        return result.scalar_one_or_none()

    async def update(self, member: OrganizationMember) -> OrganizationMember:
        """Update membership."""
        await self.session.flush()
        await self.session.refresh(member)
        return member

    async def delete(self, member_id: UUID) -> bool:
        """Delete membership."""
        result = await self.session.execute(
            delete(OrganizationMember).where(OrganizationMember.id == member_id)
        )
        return result.rowcount > 0

    async def list_members(
        self,
        org_id: UUID,
        skip: int = 0,
        limit: int = 50,
        active_only: bool = True,
    ) -> List[OrganizationMember]:
        """List organization members."""
        query = (
            select(OrganizationMember)
            .options(selectinload(OrganizationMember.user), selectinload(OrganizationMember.role))
            .where(OrganizationMember.organization_id == org_id)
        )
        if active_only:
            query = query.where(OrganizationMember.is_active == True)
        query = query.offset(skip).limit(limit).order_by(OrganizationMember.joined_at.desc())
        result = await self.session.execute(query)
        return result.scalars().all()

    async def count_members(self, org_id: UUID, active_only: bool = True) -> int:
        """Count organization members."""
        query = select(func.count(OrganizationMember.id)).where(OrganizationMember.organization_id == org_id)
        if active_only:
            query = query.where(OrganizationMember.is_active == True)
        result = await self.session.execute(query)
        return result.scalar() or 0

    async def get_user_organizations(self, user_id: UUID) -> List[OrganizationMember]:
        """Get all active organization memberships for a user."""
        result = await self.session.execute(
            select(OrganizationMember)
            .options(selectinload(OrganizationMember.organization))
            .where(OrganizationMember.user_id == user_id, OrganizationMember.is_active == True)
        )
        return result.scalars().all()

    async def is_owner(self, org_id: UUID, user_id: UUID) -> bool:
        """Check if user is owner of organization."""
        result = await self.session.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == user_id,
                OrganizationMember.is_active == True,
                OrganizationMember.role_name == MemberRole.OWNER,
            )
        )
        return result.scalar_one_or_none() is not None

    async def is_admin_or_owner(self, org_id: UUID, user_id: UUID) -> bool:
        """Check if user is admin or owner of organization."""
        result = await self.session.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == user_id,
                OrganizationMember.is_active == True,
                OrganizationMember.role_name.in_([MemberRole.OWNER, MemberRole.ADMINISTRATOR]),
            )
        )
        return result.scalar_one_or_none() is not None

    async def has_role(self, org_id: UUID, user_id: UUID, roles: List[MemberRole]) -> bool:
        """Check if user has any of the specified roles."""
        result = await self.session.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == user_id,
                OrganizationMember.is_active == True,
                OrganizationMember.role_name.in_(roles),
            )
        )
        return result.scalar_one_or_none() is not None