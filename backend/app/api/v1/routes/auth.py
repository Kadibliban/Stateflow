"""
StateFlow Authentication Routes

Registration, login, token refresh, and logout endpoints.
"""
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.core.security import (
    create_access_token,
    create_refresh_token,
    create_token_pair,
    create_password_reset_token,
    create_email_verification_token,
    decode_token,
    decode_password_reset_token,
    decode_email_verification_token,
    get_password_hash,
    verify_password,
)
from app.models.user import RefreshToken, User, UserStatus
from app.schemas.auth import TokenResponse, UserResponse, LoginResponse

router = APIRouter()


# Dependency for getting current user
async def get_current_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
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
    if not user or user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return user


class RegisterRequest(BaseModel):
    """User registration request."""
    email: EmailStr = Field(..., description="User email address")
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    password: str = Field(..., min_length=8, max_length=128, description="Password")
    full_name: str | None = Field(None, max_length=200, description="Full name")


class LoginRequest(BaseModel):
    """User login request."""
    username: str = Field(..., description="Username or email")
    password: str = Field(..., description="Password")


class RefreshRequest(BaseModel):
    """Token refresh request."""
    refresh_token: str = Field(..., description="Refresh token")


class ForgotPasswordRequest(BaseModel):
    """Forgot password request."""
    email: EmailStr = Field(..., description="User email address")


class ResetPasswordRequest(BaseModel):
    """Reset password request."""
    token: str = Field(..., description="Password reset token")
    password: str = Field(..., min_length=8, max_length=128, description="New password")


class VerifyEmailRequest(BaseModel):
    """Verify email request."""
    token: str = Field(..., description="Email verification token")


class ResendVerificationRequest(BaseModel):
    """Resend verification email request."""
    email: EmailStr = Field(..., description="User email address")


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserResponse:
    """Register a new user."""
    # Check if user already exists
    existing_user = await session.execute(
        select(User).where(
            (User.email == request.email) | (User.username == request.username)
        )
    )
    if existing_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email or username already exists",
        )

    # Create user
    hashed_password = get_password_hash(request.password)
    user = User(
        email=request.email,
        username=request.username,
        hashed_password=hashed_password,
        full_name=request.full_name,
        status=UserStatus.ACTIVE.value,  # Auto-activate for development
        email_verified=True,  # Auto-verify for development
    )

    session.add(user)
    await session.commit()
    await session.refresh(user)

    return UserResponse.model_validate(user)


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> LoginResponse:
    """Authenticate user and return access/refresh tokens with user info."""
    # Find user by username or email
    user = await session.execute(
        select(User).where(
            (User.username == request.username) | (User.email == request.username)
        )
    )
    user = user.scalar_one_or_none()

    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not active",
        )

    # Update last login
    user.last_login_at = datetime.now(timezone.utc)

    # Create token pair
    tokens = create_token_pair(user.id)

    # Store refresh token
    refresh_token = RefreshToken(
        user_id=user.id,
        token_hash=get_password_hash(tokens.refresh_token),
        jti=decode_token(tokens.refresh_token).jti,
        expires_at=decode_token(tokens.refresh_token).exp,
    )
    session.add(refresh_token)
    await session.commit()

    return LoginResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
        expires_in=tokens.expires_in,
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TokenResponse:
    """Refresh access token using refresh token."""
    try:
        token_data = decode_token(request.refresh_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    if token_data.type != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    # Check if refresh token exists and is not revoked
    stored_token = await session.execute(
        select(RefreshToken).where(
            RefreshToken.jti == token_data.jti,
            RefreshToken.revoked == False,
        )
    )
    stored_token = stored_token.scalar_one_or_none()

    if not stored_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token revoked or expired",
        )

    # Revoke old refresh token
    stored_token.revoked = True
    stored_token.revoked_at = datetime.now(timezone.utc)

    # Get user
    user = await session.get(User, token_data.sub)
    if not user or user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Create new token pair
    tokens = create_token_pair(user.id)

    # Store new refresh token
    new_refresh_token = RefreshToken(
        user_id=user.id,
        token_hash=get_password_hash(tokens.refresh_token),
        jti=decode_token(tokens.refresh_token).jti,
        expires_at=decode_token(tokens.refresh_token).exp,
    )
    session.add(new_refresh_token)
    await session.commit()

    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
        expires_in=tokens.expires_in,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: RefreshRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """Logout user by revoking refresh token."""
    try:
        token_data = decode_token(request.refresh_token)
    except ValueError:
        # Token invalid, but we still return success for security
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    if token_data.type != "refresh":
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # Revoke refresh token
    stored_token = await session.execute(
        select(RefreshToken).where(
            RefreshToken.jti == token_data.jti,
            RefreshToken.revoked == False,
        )
    )
    stored_token = stored_token.scalar_one_or_none()

    if stored_token:
        stored_token.revoked = True
        stored_token.revoked_at = datetime.now(timezone.utc)
        await session.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/revoke-all", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_all_tokens(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """Revoke all refresh tokens for current user."""
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == current_user.id, RefreshToken.revoked == False)
        .values(revoked=True, revoked_at=datetime.now(timezone.utc))
    )
    await session.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
async def forgot_password(
    request: ForgotPasswordRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """Request password reset email."""
    # Find user by email
    user = await session.execute(
        select(User).where(User.email == request.email)
    )
    user = user.scalar_one_or_none()

    # Always return success for security (don't reveal if email exists)
    if not user:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # Generate password reset token
    reset_token = create_password_reset_token(user.id)

    # TODO: Send email with reset token
    # For now, we'll log it (in production, send via email service)
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Password reset requested", extra={"email": user.email, "reset_token": reset_token})

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    request: ResetPasswordRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """Reset password using token."""
    try:
        token_data = decode_password_reset_token(request.token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    user = await session.get(User, token_data.sub)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Update password
    user.hashed_password = get_password_hash(request.password)
    await session.commit()

    # Revoke all refresh tokens for security
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked == False)
        .values(revoked=True, revoked_at=datetime.now(timezone.utc))
    )
    await session.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/verify-email", status_code=status.HTTP_204_NO_CONTENT)
async def verify_email(
    request: VerifyEmailRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """Verify email using token."""
    try:
        token_data = decode_email_verification_token(request.token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )

    user = await session.get(User, token_data.sub)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user.email_verified = True
    if user.status == UserStatus.PENDING_VERIFICATION:
        user.status = UserStatus.ACTIVE
    await session.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/resend-verification", status_code=status.HTTP_204_NO_CONTENT)
async def resend_verification(
    request: ResendVerificationRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """Resend email verification."""
    user = await session.execute(
        select(User).where(User.email == request.email)
    )
    user = user.scalar_one_or_none()

    # Always return success for security
    if not user:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    if user.email_verified:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # Generate verification token
    verification_token = create_email_verification_token(user.id)

    # TODO: Send email with verification token
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Email verification requested", extra={"email": user.email, "verification_token": verification_token})

    return Response(status_code=status.HTTP_204_NO_CONTENT)