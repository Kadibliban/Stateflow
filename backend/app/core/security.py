"""
StateFlow Security Module

Handles authentication, password hashing, JWT token management,
and authorization utilities.
"""
import base64
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from uuid import UUID

from jose import jwt, JWTError
from passlib.hash import pbkdf2_sha256
from pydantic import BaseModel

from app.core.config import settings


def generate_jti() -> str:
    """Generate a unique JWT ID (JTI)."""
    return base64.urlsafe_b64encode(secrets.token_bytes(16)).decode().rstrip("=")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against its hash."""
    return pbkdf2_sha256.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password using PBKDF2-SHA256 (no 72-byte limit)."""
    return pbkdf2_sha256.hash(password, rounds=settings.BCRYPT_ROUNDS * 1000)


class TokenData(BaseModel):
    """JWT token payload data."""
    sub: str  # user_id
    org_id: Optional[str] = None
    roles: list[str] = []
    permissions: list[str] = []
    type: str = "access"  # "access" or "refresh"
    exp: datetime
    iat: datetime
    jti: str  # JWT ID for revocation


class TokenPair(BaseModel):
    """Access and refresh token pair."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


def create_access_token(
    user_id: UUID,
    org_id: Optional[UUID] = None,
    roles: Optional[list[str]] = None,
    permissions: Optional[list[str]] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a new JWT access token."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "sub": str(user_id),
        "org_id": str(org_id) if org_id else None,
        "roles": roles or [],
        "permissions": permissions or [],
        "type": "access",
        "exp": expire,
        "iat": now,
        "jti": generate_jti(),
    }

    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(
    user_id: UUID,
    org_id: Optional[UUID] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a new JWT refresh token."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode = {
        "sub": str(user_id),
        "org_id": str(org_id) if org_id else None,
        "roles": [],
        "permissions": [],
        "type": "refresh",
        "exp": expire,
        "iat": now,
        "jti": generate_jti(),
    }

    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_token_pair(
    user_id: UUID,
    org_id: Optional[UUID] = None,
    roles: Optional[list[str]] = None,
    permissions: Optional[list[str]] = None,
) -> TokenPair:
    """Create both access and refresh tokens."""
    access_token = create_access_token(user_id, org_id, roles, permissions)
    refresh_token = create_refresh_token(user_id, org_id)

    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


def decode_token(token: str) -> TokenData:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return TokenData(**payload)
    except JWTError as e:
        raise ValueError(f"Invalid token: {str(e)}")


def decode_token_unsafe(token: str) -> Dict[str, Any]:
    """Decode a JWT token without validation (for debugging)."""
    return jwt.get_unverified_claims(token)


def is_token_expired(token: str) -> bool:
    """Check if a token is expired without full validation."""
    try:
        payload = decode_token_unsafe(token)
        exp = payload.get("exp")
        if exp:
            return datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc)
        return True
    except Exception:
        return True


def create_password_reset_token(user_id: UUID, expires_delta: Optional[timedelta] = None) -> str:
    """Create a password reset token."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(hours=1)  # 1 hour expiry for password reset

    to_encode = {
        "sub": str(user_id),
        "type": "password_reset",
        "exp": expire,
        "iat": now,
        "jti": generate_jti(),
    }

    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_email_verification_token(user_id: UUID, expires_delta: Optional[timedelta] = None) -> str:
    """Create an email verification token."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=7)  # 7 days expiry for email verification

    to_encode = {
        "sub": str(user_id),
        "type": "email_verification",
        "exp": expire,
        "iat": now,
        "jti": generate_jti(),
    }

    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_password_reset_token(token: str) -> TokenData:
    """Decode and validate a password reset token."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        if payload.get("type") != "password_reset":
            raise ValueError("Invalid token type")
        return TokenData(**payload)
    except JWTError as e:
        raise ValueError(f"Invalid token: {str(e)}")


def decode_email_verification_token(token: str) -> TokenData:
    """Decode and validate an email verification token."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        if payload.get("type") != "email_verification":
            raise ValueError("Invalid token type")
        return TokenData(**payload)
    except JWTError as e:
        raise ValueError(f"Invalid token: {str(e)}")