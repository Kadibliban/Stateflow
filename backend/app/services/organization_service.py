"""
StateFlow Organization Service

Business logic for organization and membership management.
"""
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization, OrganizationMember, MemberRole, OrganizationStatus
from app.models.user import User, Role
from app.repositories.organization_repository import (
    OrganizationRepository,
    OrganizationMemberRepository,
)
from app.repositories.user_repository import UserRepository, RoleRepository
from app.schemas.organization import (
    OrganizationResponse,
    MemberResponse,
)


class OrganizationService:
    """Service for organization operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.org_repo = OrganizationRepository(session)
        self.member_repo = OrganizationMemberRepository(session)
        self.user_repo = UserRepository(session)
        self.role_repo = RoleRepository(session)

    async def create_organization(
        self,
        name: str,
        slug: str,
        owner_id: UUID,
        description: Optional[str] = None,
    ) -> OrganizationResponse:
        """Create a new organization with owner."""
        # Check if slug is taken
        existing = await self.org_repo.get_by_slug(slug)
        if existing:
            raise ValueError("Organization slug already taken")

        # Create organization
        org = Organization(
            name=name,
            slug=slug,
            description=description,
            status=OrganizationStatus.ACTIVE,
        )
        org = await self.org_repo.create(org)
        await self.session.flush()

        # Get or create owner role
        owner_role = await self.role_repo.get_by_name("owner")
        if not owner_role:
            owner_role = Role(name="owner", display_name="Owner", description="Organization owner", is_system=True)
            self.session.add(owner_role)
            await self.session.flush()

        # Add creator as owner
        member = OrganizationMember(
            organization_id=org.id,
            user_id=owner_id,
            role_id=owner_role.id,
            role_name=MemberRole.OWNER,
            is_active=True,
        )
        await self.member_repo.create(member)
        await self.session.commit()
        await self.session.refresh(org)

        return OrganizationResponse.model_validate(org)

    async def get_organization(self, org_id: UUID, user_id: UUID) -> OrganizationResponse:
        """Get organization by ID (with membership check)."""
        membership = await self.member_repo.get_active_by_org_and_user(org_id, user_id)
        if not membership:
            raise ValueError("Not a member of this organization")

        org = await self.org_repo.get_by_id(org_id)
        if not org or org.status == OrganizationStatus.DELETED:
            raise ValueError("Organization not found")

        return OrganizationResponse.model_validate(org)

    async def list_user_organizations(self, user_id: UUID) -> List[OrganizationResponse]:
        """List organizations user is a member of."""
        memberships = await self.member_repo.get_user_organizations(user_id)
        orgs = [m.organization for m in memberships if m.organization.status != OrganizationStatus.DELETED]
        return [OrganizationResponse.model_validate(org) for org in orgs]

    async def update_organization(
        self,
        org_id: UUID,
        user_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
    ) -> OrganizationResponse:
        """Update organization (admin/owner only)."""
        if not await self.member_repo.is_admin_or_owner(org_id, user_id):
            raise ValueError("Insufficient permissions")

        org = await self.org_repo.get_by_id(org_id)
        if not org or org.status == OrganizationStatus.DELETED:
            raise ValueError("Organization not found")

        if name is not None:
            org.name = name
        if description is not None:
            org.description = description
        if status is not None:
            org.status = OrganizationStatus(status)

        await self.org_repo.update(org)
        await self.session.commit()
        await self.session.refresh(org)

        return OrganizationResponse.model_validate(org)

    async def delete_organization(self, org_id: UUID, user_id: UUID) -> None:
        """Delete organization (owner only)."""
        if not await self.member_repo.is_owner(org_id, user_id):
            raise ValueError("Only owner can delete organization")

        await self.org_repo.delete(org_id)
        await self.session.commit()


class MembershipService:
    """Service for organization membership operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.member_repo = OrganizationMemberRepository(session)
        self.user_repo = UserRepository(session)
        self.role_repo = RoleRepository(session)
        self.org_repo = OrganizationRepository(session)

    async def invite_member(
        self,
        org_id: UUID,
        inviter_id: UUID,
        email: str,
        role_name: str,
    ) -> MemberResponse:
        """Invite a member to organization (admin/owner only)."""
        if not await self.member_repo.is_admin_or_owner(org_id, inviter_id):
            raise ValueError("Insufficient permissions")

        # Find user by email
        user = await self.user_repo.get_by_email(email)
        if not user:
            raise ValueError("User not found")

        # Check if already a member
        existing = await self.member_repo.get_by_org_and_user(org_id, user.id)
        if existing:
            raise ValueError("User is already a member")

        # Validate role
        try:
            role_enum = MemberRole(role_name)
        except ValueError:
            raise ValueError("Invalid role")

        role = await self.role_repo.get_by_name(role_name)
        if not role:
            raise ValueError("Role not found")

        # Create membership
        member = OrganizationMember(
            organization_id=org_id,
            user_id=user.id,
            role_id=role.id,
            role_name=role_enum,
            invited_by=inviter_id,
            is_active=True,
        )
        member = await self.member_repo.create(member)
        await self.session.commit()

        # Load relationships
        await self.session.refresh(member, ["user", "role"])
        return self._to_member_response(member)

    async def list_members(self, org_id: UUID, user_id: UUID) -> List[MemberResponse]:
        """List organization members."""
        membership = await self.member_repo.get_active_by_org_and_user(org_id, user_id)
        if not membership:
            raise ValueError("Not a member of this organization")

        members = await self.member_repo.list_members(org_id)
        return [self._to_member_response(m) for m in members]

    async def update_member(
        self,
        org_id: UUID,
        member_id: UUID,
        actor_id: UUID,
        role_name: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> MemberResponse:
        """Update member role or status (owner only)."""
        if not await self.member_repo.is_owner(org_id, actor_id):
            raise ValueError("Only owner can update members")

        member = await self.member_repo.get_by_id(member_id)
        if not member or member.organization_id != org_id:
            raise ValueError("Member not found")

        # Prevent owner from changing their own role
        if member.user_id == actor_id and role_name and role_name != "owner":
            raise ValueError("Owner cannot change their own role")

        if role_name is not None:
            try:
                role_enum = MemberRole(role_name)
            except ValueError:
                raise ValueError("Invalid role")

            role = await self.role_repo.get_by_name(role_name)
            if not role:
                raise ValueError("Role not found")
            member.role_id = role.id
            member.role_name = role_enum

        if is_active is not None:
            member.is_active = is_active

        member = await self.member_repo.update(member)
        await self.session.commit()

        # Load relationships
        await self.session.refresh(member, ["user", "role"])
        return self._to_member_response(member)

    async def remove_member(self, org_id: UUID, member_id: UUID, actor_id: UUID) -> None:
        """Remove member from organization (owner only)."""
        if not await self.member_repo.is_owner(org_id, actor_id):
            raise ValueError("Only owner can remove members")

        member = await self.member_repo.get_by_id(member_id)
        if not member or member.organization_id != org_id:
            raise ValueError("Member not found")

        # Prevent owner from removing themselves
        if member.user_id == actor_id:
            raise ValueError("Owner cannot remove themselves")

        await self.member_repo.delete(member_id)
        await self.session.commit()

    def _to_member_response(self, member: OrganizationMember) -> MemberResponse:
        """Convert member to response schema."""
        return MemberResponse(
            id=member.id,
            organization_id=member.organization_id,
            user_id=member.user_id,
            role_id=member.role_id,
            role_name=member.role_name.value,
            joined_at=member.joined_at,
            invited_by=member.invited_by,
            is_active=member.is_active,
            user_email=member.user.email,
            user_username=member.user.username,
            user_full_name=member.user.full_name,
        )