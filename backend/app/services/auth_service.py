"""
StateFlow Auth Service

Business logic for authentication and user management.
"""
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    create_token_pair,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.models.user import User, Role, Permission, RefreshToken, UserStatus
from app.repositories.user_repository import (
    UserRepository,
    RoleRepository,
    PermissionRepository,
    RefreshTokenRepository,
)
from app.schemas.auth import UserResponse, TokenResponse


class AuthService:
    """Service for authentication operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.role_repo = RoleRepository(session)
        self.permission_repo = PermissionRepository(session)
        self.token_repo = RefreshTokenRepository(session)

    async def register_user(
        self,
        email: str,
        username: str,
        password: str,
        full_name: Optional[str] = None,
    ) -> UserResponse:
        """Register a new user."""
        # Check if user exists
        existing = await self.user_repo.get_by_email_or_username(email)
        if existing:
            raise ValueError("User with this email or username already exists")

        # Hash password
        hashed_password = get_password_hash(password)

        # Create user
        user = User(
            email=email,
            username=username,
            hashed_password=hashed_password,
            full_name=full_name,
            status=UserStatus.ACTIVE,
            email_verified=True,  # Auto-verify for development
        )

        user = await self.user_repo.create(user)
        await self.session.commit()

        return UserResponse.model_validate(user)

    async def authenticate_user(self, username: str, password: str) -> TokenResponse:
        """Authenticate user and return tokens."""
        user = await self.user_repo.get_by_email_or_username(username)
        if not user or not verify_password(password, user.hashed_password):
            raise ValueError("Invalid credentials")

        if user.status != UserStatus.ACTIVE:
            raise ValueError("Account is not active")

        # Update last login
        await self.user_repo.update_last_login(user.id)

        # Create token pair
        tokens = create_token_pair(user.id)

        # Store refresh token
        refresh_token = RefreshToken(
            user_id=user.id,
            token_hash=get_password_hash(tokens.refresh_token),
            jti=decode_token(tokens.refresh_token).jti,
            expires_at=decode_token(tokens.refresh_token).exp,
        )
        await self.token_repo.create(refresh_token)
        await self.session.commit()

        return TokenResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            token_type=tokens.token_type,
            expires_in=tokens.expires_in,
        )

    async def refresh_tokens(self, refresh_token: str) -> TokenResponse:
        """Refresh access token using refresh token."""
        try:
            token_data = decode_token(refresh_token)
        except ValueError:
            raise ValueError("Invalid refresh token")

        if token_data.type != "refresh":
            raise ValueError("Invalid token type")

        # Check if refresh token exists and is valid
        stored_token = await self.token_repo.get_valid_by_jti(token_data.jti)
        if not stored_token:
            raise ValueError("Refresh token revoked or expired")

        # Revoke old refresh token
        await self.token_repo.revoke(token_data.jti)

        # Get user
        user = await self.user_repo.get_by_id(UUID(token_data.sub))
        if not user or user.status != UserStatus.ACTIVE:
            raise ValueError("User not found or inactive")

        # Create new token pair
        tokens = create_token_pair(user.id)

        # Store new refresh token
        new_refresh_token = RefreshToken(
            user_id=user.id,
            token_hash=get_password_hash(tokens.refresh_token),
            jti=decode_token(tokens.refresh_token).jti,
            expires_at=decode_token(tokens.refresh_token).exp,
        )
        await self.token_repo.create(new_refresh_token)
        await self.session.commit()

        return TokenResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            token_type=tokens.token_type,
            expires_in=tokens.expires_in,
        )

    async def logout(self, refresh_token: str) -> None:
        """Logout user by revoking refresh token."""
        try:
            token_data = decode_token(refresh_token)
        except ValueError:
            return  # Silent success for security

        if token_data.type != "refresh":
            return

        await self.token_repo.revoke(token_data.jti)
        await self.session.commit()

    async def revoke_all_tokens(self, user_id: UUID) -> int:
        """Revoke all refresh tokens for user."""
        count = await self.token_repo.revoke_all_for_user(user_id)
        await self.session.commit()
        return count

    async def get_current_user(self, access_token: str) -> User:
        """Get current user from access token."""
        try:
            token_data = decode_token(access_token)
        except ValueError:
            raise ValueError("Invalid token")

        if token_data.type != "access":
            raise ValueError("Invalid token type")

        user = await self.user_repo.get_by_id(UUID(token_data.sub))
        if not user or user.status != UserStatus.ACTIVE:
            raise ValueError("User not found or inactive")

        return user

    async def change_password(self, user_id: UUID, old_password: str, new_password: str) -> bool:
        """Change user password."""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        if not verify_password(old_password, user.hashed_password):
            raise ValueError("Current password is incorrect")

        user.hashed_password = get_password_hash(new_password)
        await self.user_repo.update(user)

        # Revoke all existing tokens
        await self.revoke_all_tokens(user_id)

        await self.session.commit()
        return True

    async def cleanup_expired_tokens(self) -> int:
        """Clean up expired refresh tokens."""
        count = await self.token_repo.cleanup_expired()
        await self.session.commit()
        return count

    # Role and permission management
    async def create_role(self, name: str, display_name: str, description: Optional[str] = None) -> Role:
        """Create a new role."""
        existing = await self.role_repo.get_by_name(name)
        if existing:
            raise ValueError("Role already exists")

        role = Role(name=name, display_name=display_name, description=description)
        role = await self.role_repo.create(role)
        await self.session.commit()
        return role

    async def create_permission(
        self, name: str, display_name: str, resource: str, action: str, description: Optional[str] = None
    ) -> Permission:
        """Create a new permission."""
        existing = await self.permission_repo.get_by_name(name)
        if existing:
            raise ValueError("Permission already exists")

        permission = Permission(
            name=name,
            display_name=display_name,
            resource=resource,
            action=action,
            description=description,
        )
        permission = await self.permission_repo.create(permission)
        await self.session.commit()
        return permission

    async def assign_permissions_to_role(self, role_name: str, permission_names: List[str]) -> Role:
        """Assign permissions to a role."""
        role = await self.role_repo.get_by_name(role_name)
        if not role:
            raise ValueError("Role not found")

        permissions = await self.permission_repo.list_permissions()
        perm_map = {p.name: p for p in permissions}

        for perm_name in permission_names:
            if perm_name not in perm_map:
                raise ValueError(f"Permission {perm_name} not found")

        permission_ids = [perm_map[p].id for p in permission_names]
        await self.role_repo.assign_permissions(role.id, permission_ids)
        await self.session.commit()

        # Refresh role with permissions
        return await self.role_repo.get_by_id(role.id)