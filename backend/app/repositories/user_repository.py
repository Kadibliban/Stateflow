"""
StateFlow User Repository

Data access layer for users, roles, permissions, and refresh tokens.
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User, Role, Permission, RefreshToken, UserStatus


class UserRepository:
    """Repository for user operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user: User) -> User:
        """Create a new user."""
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID."""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        result = await self.session.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()

    async def get_by_email_or_username(self, identifier: str) -> Optional[User]:
        """Get user by email or username."""
        result = await self.session.execute(
            select(User).where(
                (User.email == identifier) | (User.username == identifier)
            )
        )
        return result.scalar_one_or_none()

    async def update(self, user: User) -> User:
        """Update user."""
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def delete(self, user_id: UUID) -> bool:
        """Delete user."""
        result = await self.session.execute(
            delete(User).where(User.id == user_id)
        )
        return result.rowcount > 0

    async def list_users(
        self,
        skip: int = 0,
        limit: int = 20,
        status: Optional[UserStatus] = None,
    ) -> List[User]:
        """List users with pagination."""
        query = select(User)
        if status:
            query = query.where(User.status == status)
        query = query.offset(skip).limit(limit).order_by(User.created_at.desc())
        result = await self.session.execute(query)
        return result.scalars().all()

    async def update_last_login(self, user_id: UUID) -> None:
        """Update user's last login timestamp."""
        from datetime import datetime, timezone
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(last_login_at=datetime.now(timezone.utc))
        )


class RoleRepository:
    """Repository for role operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, role: Role) -> Role:
        """Create a new role."""
        self.session.add(role)
        await self.session.flush()
        await self.session.refresh(role)
        return role

    async def get_by_id(self, role_id: UUID) -> Optional[Role]:
        """Get role by ID."""
        result = await self.session.execute(
            select(Role).where(Role.id == role_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Optional[Role]:
        """Get role by name."""
        result = await self.session.execute(
            select(Role).where(Role.name == name)
        )
        return result.scalar_one_or_none()

    async def list_roles(self) -> List[Role]:
        """List all roles."""
        result = await self.session.execute(select(Role).order_by(Role.name))
        return result.scalars().all()

    async def assign_permissions(self, role_id: UUID, permission_ids: List[UUID]) -> Role:
        """Assign permissions to role."""
        role = await self.get_by_id(role_id)
        if not role:
            raise ValueError("Role not found")

        permissions = await self.session.execute(
            select(Permission).where(Permission.id.in_(permission_ids))
        )
        role.permissions = permissions.scalars().all()
        await self.session.flush()
        return role


class PermissionRepository:
    """Repository for permission operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, permission: Permission) -> Permission:
        """Create a new permission."""
        self.session.add(permission)
        await self.session.flush()
        await self.session.refresh(permission)
        return permission

    async def get_by_id(self, permission_id: UUID) -> Optional[Permission]:
        """Get permission by ID."""
        result = await self.session.execute(
            select(Permission).where(Permission.id == permission_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Optional[Permission]:
        """Get permission by name."""
        result = await self.session.execute(
            select(Permission).where(Permission.name == name)
        )
        return result.scalar_one_or_none()

    async def list_permissions(self) -> List[Permission]:
        """List all permissions."""
        result = await self.session.execute(select(Permission).order_by(Permission.resource, Permission.action))
        return result.scalars().all()


class RefreshTokenRepository:
    """Repository for refresh token operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, token: RefreshToken) -> RefreshToken:
        """Create a new refresh token."""
        self.session.add(token)
        await self.session.flush()
        await self.session.refresh(token)
        return token

    async def get_by_jti(self, jti: str) -> Optional[RefreshToken]:
        """Get refresh token by JWT ID."""
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.jti == jti)
        )
        return result.scalar_one_or_none()

    async def get_valid_by_jti(self, jti: str) -> Optional[RefreshToken]:
        """Get valid (non-revoked, non-expired) refresh token by JWT ID."""
        from datetime import datetime, timezone
        result = await self.session.execute(
            select(RefreshToken).where(
                RefreshToken.jti == jti,
                RefreshToken.revoked == False,
                RefreshToken.expires_at > datetime.now(timezone.utc),
            )
        )
        return result.scalar_one_or_none()

    async def revoke(self, jti: str) -> bool:
        """Revoke a refresh token."""
        from datetime import datetime, timezone
        result = await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.jti == jti, RefreshToken.revoked == False)
            .values(revoked=True, revoked_at=datetime.now(timezone.utc))
        )
        return result.rowcount > 0

    async def revoke_all_for_user(self, user_id: UUID) -> int:
        """Revoke all refresh tokens for a user."""
        from datetime import datetime, timezone
        result = await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked == False)
            .values(revoked=True, revoked_at=datetime.now(timezone.utc))
        )
        return result.rowcount

    async def cleanup_expired(self) -> int:
        """Delete expired refresh tokens."""
        from datetime import datetime, timezone
        result = await self.session.execute(
            delete(RefreshToken).where(RefreshToken.expires_at < datetime.now(timezone.utc))
        )
        return result.rowcount