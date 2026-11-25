"""
StateFlow Authorization Middleware

Role-based access control and permission checking middleware.
"""
from typing import Callable, List, Optional, Set
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_session
from app.core.security import decode_token
from app.models.organization import OrganizationMember, MemberRole
from app.models.user import User, Role, Permission


async def get_current_user_from_token(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User:
    """Get current authenticated user from access token."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
        )

    token = auth_header.split(" ")[1]
    try:
        token_data = decode_token(token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    if token_data.type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user = await session.get(User, token_data.sub)
    if not user or user.status.value != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return user


async def get_current_organization(
    request: Request,
    current_user: User = Depends(get_current_user_from_token),
    session: AsyncSession = Depends(get_session),
) -> Optional[UUID]:
    """Get current organization ID from token or header."""
    # Try to get from token
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            token_data = decode_token(token)
            if token_data.org_id:
                return UUID(token_data.org_id)
        except ValueError:
            pass

    # Try to get from header
    org_header = request.headers.get("X-Organization-ID")
    if org_header:
        try:
            return UUID(org_header)
        except ValueError:
            pass

    return None


async def get_user_permissions(
    user: User,
    organization_id: Optional[UUID],
    session: AsyncSession,
) -> Set[str]:
    """Get all permissions for a user in an organization."""
    permissions = set()

    if not organization_id:
        return permissions

    # Get user's membership in the organization
    result = await session.execute(
        select(OrganizationMember)
        .options(
            selectinload(OrganizationMember.role).selectinload(Role.permissions)
        )
        .where(
            OrganizationMember.user_id == user.id,
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.is_active == True,
        )
    )
    membership = result.scalar_one_or_none()

    if not membership:
        return permissions

    # Add role permissions
    for perm in membership.role.permissions:
        permissions.add(f"{perm.resource}:{perm.action}")

    # Add member role as permission
    permissions.add(f"role:{membership.role_name.value}")

    return permissions


def require_permissions(*required_permissions: str):
    """Dependency that checks if user has required permissions."""
    async def permission_checker(
        request: Request,
        current_user: User = Depends(get_current_user_from_token),
        session: AsyncSession = Depends(get_session),
    ) -> User:
        org_id = await get_current_organization(request, current_user, session)
        user_perms = await get_user_permissions(current_user, org_id, session)

        # Superuser has all permissions
        if current_user.is_superuser:
            return current_user

        # Check if user has all required permissions
        missing = set(required_permissions) - user_perms
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permissions: {', '.join(missing)}",
            )

        return current_user

    return permission_checker


def require_organization_role(*allowed_roles: MemberRole):
    """Dependency that checks if user has required organization role."""
    async def role_checker(
        request: Request,
        current_user: User = Depends(get_current_user_from_token),
        session: AsyncSession = Depends(get_session),
    ) -> User:
        org_id = await get_current_organization(request, current_user, session)

        if not org_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization context required",
            )

        # Superuser bypasses role checks
        if current_user.is_superuser:
            return current_user

        result = await session.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == current_user.id,
                OrganizationMember.is_active == True,
                OrganizationMember.role_name.in_(allowed_roles),
            )
        )
        membership = result.scalar_one_or_none()

        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {', '.join(r.value for r in allowed_roles)}",
            )

        return current_user

    return role_checker


# Convenience dependencies
require_owner = require_organization_role(MemberRole.OWNER)
require_admin_or_owner = require_organization_role(MemberRole.ADMINISTRATOR, MemberRole.OWNER)
require_developer_or_admin = require_organization_role(
    MemberRole.DEVELOPER, MemberRole.ADMINISTRATOR, MemberRole.OWNER
)


class PermissionChecker:
    """Helper class for checking permissions in service layer."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_permissions(
        self, user_id: UUID, organization_id: UUID
    ) -> Set[str]:
        """Get all permissions for a user in an organization."""
        result = await self.session.execute(
            select(OrganizationMember)
            .options(
                selectinload(OrganizationMember.role).selectinload(Role.permissions)
            )
            .where(
                OrganizationMember.user_id == user_id,
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.is_active == True,
            )
        )
        membership = result.scalar_one_or_none()

        if not membership:
            return set()

        permissions = set()
        for perm in membership.role.permissions:
            permissions.add(f"{perm.resource}:{perm.action}")
        permissions.add(f"role:{membership.role_name.value}")

        return permissions

    async def has_permission(
        self, user_id: UUID, organization_id: UUID, permission: str
    ) -> bool:
        """Check if user has a specific permission."""
        perms = await self.get_user_permissions(user_id, organization_id)
        return permission in perms

    async def has_any_permission(
        self, user_id: UUID, organization_id: UUID, permissions: List[str]
    ) -> bool:
        """Check if user has any of the specified permissions."""
        user_perms = await self.get_user_permissions(user_id, organization_id)
        return bool(set(permissions) & user_perms)

    async def has_role(
        self, user_id: UUID, organization_id: UUID, roles: List[MemberRole]
    ) -> bool:
        """Check if user has any of the specified roles."""
        result = await self.session.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == user_id,
                OrganizationMember.is_active == True,
                OrganizationMember.role_name.in_(roles),
            )
        )
        return result.scalar_one_or_none() is not None

    async def is_owner(self, user_id: UUID, organization_id: UUID) -> bool:
        """Check if user is owner of organization."""
        return await self.has_role(user_id, organization_id, [MemberRole.OWNER])

    async def is_admin_or_owner(self, user_id: UUID, organization_id: UUID) -> bool:
        """Check if user is admin or owner of organization."""
        return await self.has_role(
            user_id, organization_id, [MemberRole.ADMINISTRATOR, MemberRole.OWNER]
        )