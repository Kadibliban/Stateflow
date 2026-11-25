"""
StateFlow Authentication Tests

Unit tests for authentication endpoints and security features.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.models.user import User, UserStatus


class TestPasswordHashing:
    """Tests for password hashing and verification."""

    def test_password_hash_and_verify(self):
        """Test password hashing and verification."""
        password = "secure_password_123"
        hashed = get_password_hash(password)

        assert hashed != password
        assert verify_password(password, hashed)
        assert not verify_password("wrong_password", hashed)

    def test_password_hash_different_each_time(self):
        """Test that hashing the same password produces different hashes."""
        password = "test_password"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)

        assert hash1 != hash2
        assert verify_password(password, hash1)
        assert verify_password(password, hash2)


class TestTokenCreation:
    """Tests for JWT token creation and decoding."""

    def test_create_access_token(self):
        """Test creating an access token."""
        from uuid import uuid4
        user_id = uuid4()

        token = create_access_token(user_id)
        assert isinstance(token, str)
        assert len(token) > 0

        # Decode and verify
        token_data = decode_token(token)
        assert token_data.sub == str(user_id)
        assert token_data.type == "access"
        assert token_data.jti is not None

    def test_create_refresh_token(self):
        """Test creating a refresh token."""
        from uuid import uuid4
        user_id = uuid4()

        token = create_refresh_token(user_id)
        assert isinstance(token, str)
        assert len(token) > 0

        token_data = decode_token(token)
        assert token_data.sub == str(user_id)
        assert token_data.type == "refresh"

    def test_create_token_pair(self):
        """Test creating access and refresh token pair."""
        from uuid import uuid4
        user_id = uuid4()

        pair = create_token_pair(user_id)
        assert pair.access_token
        assert pair.refresh_token
        assert pair.token_type == "bearer"
        assert pair.expires_in > 0

        # Verify both tokens
        access_data = decode_token(pair.access_token)
        refresh_data = decode_token(pair.refresh_token)

        assert access_data.sub == str(user_id)
        assert access_data.type == "access"
        assert refresh_data.sub == str(user_id)
        assert refresh_data.type == "refresh"

    def test_password_reset_token(self):
        """Test creating and decoding password reset token."""
        from uuid import uuid4
        user_id = uuid4()

        token = create_password_reset_token(user_id)
        token_data = decode_password_reset_token(token)

        assert token_data.sub == str(user_id)
        assert token_data.type == "password_reset"

    def test_email_verification_token(self):
        """Test creating and decoding email verification token."""
        from uuid import uuid4
        user_id = uuid4()

        token = create_email_verification_token(user_id)
        token_data = decode_email_verification_token(token)

        assert token_data.sub == str(user_id)
        assert token_data.type == "email_verification"

    def test_invalid_token_type_rejection(self):
        """Test that wrong token types are rejected by specific decode functions."""
        from uuid import uuid4
        user_id = uuid4()

        # Create access token, try to decode as password reset
        access_token = create_access_token(user_id)
        with pytest.raises(ValueError, match="Invalid token type"):
            decode_password_reset_token(access_token)

        # Create access token, try to decode as email verification
        with pytest.raises(ValueError, match="Invalid token type"):
            decode_email_verification_token(access_token)

        # Create password reset token, try to decode as email verification
        reset_token = create_password_reset_token(user_id)
        with pytest.raises(ValueError, match="Invalid token type"):
            decode_email_verification_token(reset_token)

        # Create email verification token, try to decode as password reset
        verify_token = create_email_verification_token(user_id)
        with pytest.raises(ValueError, match="Invalid token type"):
            decode_password_reset_token(verify_token)


class TestAuthenticationEndpoints:
    """Tests for authentication API endpoints."""

    def test_register_user(self, client: TestClient):
        """Test user registration."""
        print("DEBUG: test_register_user START")
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "username": "newuser",
                "password": "password123",
                "full_name": "New User",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["username"] == "newuser"
        assert data["full_name"] == "New User"
        assert data["status"] == "active"
        assert data["email_verified"] is True

    def test_register_duplicate_email(self, client: TestClient):
        """Test registration with duplicate email fails."""
        # First, register a user
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "duplicate@example.com",
                "username": "firstuser",
                "password": "password123",
            },
        )
        assert response.status_code == 201

        # Try to register with same email
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "duplicate@example.com",
                "username": "different_user",
                "password": "password123",
            },
        )
        assert response.status_code == 409

    def test_register_duplicate_username(self, client: TestClient):
        """Test registration with duplicate username fails."""
        # First, register a user
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "first@example.com",
                "username": "duplicateuser",
                "password": "password123",
            },
        )
        assert response.status_code == 201

        # Try to register with same username
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "different@example.com",
                "username": "duplicateuser",
                "password": "password123",
            },
        )
        assert response.status_code == 409

    def test_login_success(self, client: TestClient):
        """Test successful login."""
        # Register a user first
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "loginuser@example.com",
                "username": "loginuser",
                "password": "password123",
            },
        )
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "loginuser", "password": "password123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

    def test_login_wrong_password(self, client: TestClient):
        """Test login with wrong password fails."""
        # Register a user first
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "wrongpass@example.com",
                "username": "wrongpassuser",
                "password": "password123",
            },
        )
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "wrongpassuser", "password": "wrong_password"},
        )
        assert response.status_code == 401

    def test_login_nonexistent_user(self, client: TestClient):
        """Test login with nonexistent user fails."""
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "nonexistent", "password": "password123"},
        )
        assert response.status_code == 401

    def test_refresh_token(self, client: TestClient):
        """Test token refresh."""
        # Register and login first
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "refresh@example.com",
                "username": "refreshuser",
                "password": "password123",
            },
        )
        login_response = client.post(
            "/api/v1/auth/login",
            json={"username": "refreshuser", "password": "password123"},
        )
        tokens = login_response.json()
        refresh_token = tokens["refresh_token"]

        # Refresh token
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["access_token"] != tokens["access_token"]
        assert data["refresh_token"] != tokens["refresh_token"]

    async def test_refresh_revoked_token(self, client: TestClient, db_session: AsyncSession):
        """Test that revoked refresh token cannot be used."""
        from app.models.user import RefreshToken
        from app.core.security import decode_token
        from sqlalchemy import select

        # Register and login first
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "revoked@example.com",
                "username": "revokeduser",
                "password": "password123",
            },
        )
        login_response = client.post(
            "/api/v1/auth/login",
            json={"username": "revokeduser", "password": "password123"},
        )
        tokens = login_response.json()

        # Get the refresh token that was created during login and revoke it
        jti = decode_token(tokens["refresh_token"]).jti
        result = await db_session.execute(
            select(RefreshToken).where(RefreshToken.jti == jti)
        )
        refresh_token_obj = result.scalar_one()
        refresh_token_obj.revoked = True
        # Commit the transaction so the revoked token is visible to the TestClient's session
        await db_session._test_trans.commit()

        # Try to use revoked token
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert response.status_code == 401

    def test_logout(self, client: TestClient):
        """Test logout revokes refresh token."""
        # Register and login first
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "logout@example.com",
                "username": "logoutuser",
                "password": "password123",
            },
        )
        login_response = client.post(
            "/api/v1/auth/login",
            json={"username": "logoutuser", "password": "password123"},
        )
        tokens = login_response.json()

        # Logout
        response = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert response.status_code == 204

        # Try to use logged out token
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert response.status_code == 401

    def test_revoke_all_tokens(self, client: TestClient):
        """Test revoking all tokens for current user."""
        # Register and login first
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "revokeall@example.com",
                "username": "revokealluser",
                "password": "password123",
            },
        )
        login_response = client.post(
            "/api/v1/auth/login",
            json={"username": "revokealluser", "password": "password123"},
        )
        tokens = login_response.json()

        # Revoke all tokens
        response = client.post(
            "/api/v1/auth/revoke-all",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert response.status_code == 204


class TestPasswordReset:
    """Tests for password reset flow."""

    def test_forgot_password(self, client: TestClient, test_user: User):
        """Test forgot password request."""
        response = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": test_user.email},
        )
        # Always returns 204 for security
        assert response.status_code == 204

    def test_forgot_password_nonexistent(self, client: TestClient):
        """Test forgot password for nonexistent user."""
        response = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "nonexistent@example.com"},
        )
        # Always returns 204 for security
        assert response.status_code == 204

    def test_reset_password(self, client: TestClient, test_user: User):
        """Test password reset with valid token."""
        from app.core.security import create_password_reset_token

        # Create reset token
        reset_token = create_password_reset_token(test_user.id)

        # Reset password
        response = client.post(
            "/api/v1/auth/reset-password",
            json={"token": reset_token, "password": "new_password_123"},
        )
        assert response.status_code == 204

        # Verify new password works
        response = client.post(
            "/api/v1/auth/login",
            json={"username": test_user.username, "password": "new_password_123"},
        )
        assert response.status_code == 200

    def test_reset_password_invalid_token(self, client: TestClient):
        """Test password reset with invalid token."""
        response = client.post(
            "/api/v1/auth/reset-password",
            json={"token": "invalid_token", "password": "new_password_123"},
        )
        assert response.status_code == 400

    def test_reset_password_expired_token(self, client: TestClient, test_user: User):
        """Test password reset with expired token."""
        from app.core.security import create_password_reset_token
        from datetime import timedelta

        # Create expired token
        reset_token = create_password_reset_token(test_user.id, expires_delta=timedelta(seconds=-1))

        response = client.post(
            "/api/v1/auth/reset-password",
            json={"token": reset_token, "password": "new_password_123"},
        )
        assert response.status_code == 400


class TestEmailVerification:
    """Tests for email verification flow."""

    def test_verify_email(self, client: TestClient, test_user: User, db_session: AsyncSession):
        """Test email verification with valid token."""
        from app.core.security import create_email_verification_token

        # Create user with unverified email
        test_user.email_verified = False
        test_user.status = UserStatus.PENDING_VERIFICATION
        # Note: commit happens via fixture

        # Create verification token
        verification_token = create_email_verification_token(test_user.id)

        # Verify email
        response = client.post(
            "/api/v1/auth/verify-email",
            json={"token": verification_token},
        )
        assert response.status_code == 204

        # Verify user is now active and verified
        # Note: we can't await refresh in sync test, but we can check via new request
        response = client.post(
            "/api/v1/auth/login",
            json={"username": test_user.username, "password": "password123"},
        )
        assert response.status_code == 200

    def test_verify_email_invalid_token(self, client: TestClient):
        """Test email verification with invalid token."""
        response = client.post(
            "/api/v1/auth/verify-email",
            json={"token": "invalid_token"},
        )
        assert response.status_code == 400

    def test_resend_verification(self, client: TestClient, test_user: User, db_session: AsyncSession):
        """Test resending verification email."""
        # Make user unverified
        test_user.email_verified = False
        # Note: commit happens via fixture

        response = client.post(
            "/api/v1/auth/resend-verification",
            json={"email": test_user.email},
        )
        assert response.status_code == 204

    def test_resend_verification_already_verified(self, client: TestClient, test_user: User):
        """Test resending verification for already verified user."""
        response = client.post(
            "/api/v1/auth/resend-verification",
            json={"email": test_user.email},
        )
        assert response.status_code == 204