"""
StateFlow Organization Tests

Unit tests for organization and membership management.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from uuid import uuid4

from app.models.organization import Organization, OrganizationMember, MemberRole, OrganizationStatus
from app.models.user import User, UserStatus, Role
from app.core.security import get_password_hash
from app.core.config import settings


def get_test_session():
    """Create a test database session."""
    test_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    TestingSessionLocal = sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    return TestingSessionLocal, test_engine


class TestOrganizationEndpoints:
    """Tests for organization API endpoints."""

    @pytest.mark.asyncio
    async def test_create_organization(self, async_client: AsyncClient, auth_headers: dict):
        """Test creating an organization."""
        response = await async_client.post(
            "/api/v1/organizations",
            json={
                "name": "New Organization",
                "slug": "new-org",
                "description": "A new organization",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Organization"
        assert data["slug"] == "new-org"
        assert data["description"] == "A new organization"
        assert data["status"] == "active"

    @pytest.mark.asyncio
    async def test_create_organization_duplicate_slug(self, async_client: AsyncClient, auth_headers: dict, test_organization: Organization):
        """Test creating organization with duplicate slug fails."""
        response = await async_client.post(
            "/api/v1/organizations",
            json={
                "name": "Another Organization",
                "slug": test_organization.slug,
                "description": "Another org",
            },
            headers=auth_headers,
        )
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_list_organizations(self, async_client: AsyncClient, test_user: User, test_organization: Organization):
        """Test listing user's organizations."""
        # Login as test_user (owner of test_organization)
        from app.core.security import create_token_pair
        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        response = await async_client.get(
            "/api/v1/organizations",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        org_slugs = [org["slug"] for org in data]
        assert test_organization.slug in org_slugs

    @pytest.mark.asyncio
    async def test_get_organization(self, async_client: AsyncClient, test_user: User, test_organization: Organization):
        """Test getting organization by ID."""
        from app.core.security import create_token_pair
        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        response = await async_client.get(
            f"/api/v1/organizations/{test_organization.id}",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_organization.id)
        assert data["name"] == test_organization.name

    @pytest.mark.asyncio
    async def test_get_organization_not_member(self, async_client: AsyncClient, test_user: User, test_organization: Organization):
        """Test getting organization user is not a member of."""
        # Create another user using a separate session
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import NullPool
        from app.core.config import settings

        test_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
        TestingSessionLocal = sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

        async with TestingSessionLocal() as session:
            other_user = User(
                email="other@example.com",
                username="otheruser",
                hashed_password=get_password_hash("password123"),
                status=UserStatus.ACTIVE,
                email_verified=True,
            )
            session.add(other_user)
            await session.commit()
            await session.refresh(other_user)

        await test_engine.dispose()

        # Login as other user
        login_response = await async_client.post(
            "/api/v1/auth/login",
            json={"username": "otheruser", "password": "password123"},
        )
        tokens = login_response.json()
        other_headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        # Try to access organization
        response = await async_client.get(
            f"/api/v1/organizations/{test_organization.id}",
            headers=other_headers,
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_update_organization(self, async_client: AsyncClient, test_user: User, test_organization: Organization):
        """Test updating organization."""
        from app.core.security import create_token_pair
        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        response = await async_client.patch(
            f"/api/v1/organizations/{test_organization.id}",
            json={
                "name": "Updated Organization",
                "description": "Updated description",
            },
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Organization"
        assert data["description"] == "Updated description"

    @pytest.mark.asyncio
    async def test_update_organization_not_admin(self, async_client: AsyncClient, test_organization: Organization):
        """Test updating organization without admin permission fails."""
        # Create another user and add as viewer using a separate session
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import NullPool
        from app.core.config import settings

        test_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
        TestingSessionLocal = sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

        async with TestingSessionLocal() as session:
            other_user = User(
                email="viewer@example.com",
                username="viewer",
                hashed_password=get_password_hash("password123"),
                status=UserStatus.ACTIVE,
                email_verified=True,
            )
            session.add(other_user)
            await session.flush()

            # Get viewer role
            viewer_role = await session.execute(
                select(Role).where(Role.name == "viewer")
            )
            viewer_role = viewer_role.scalar_one()

            # Add as viewer
            member = OrganizationMember(
                organization_id=test_organization.id,
                user_id=other_user.id,
                role_id=viewer_role.id,
                role_name=MemberRole.VIEWER,
                is_active=True,
            )
            session.add(member)
            await session.commit()

        await test_engine.dispose()

        # Login as viewer
        login_response = await async_client.post(
            "/api/v1/auth/login",
            json={"username": "viewer", "password": "password123"},
        )
        tokens = login_response.json()
        viewer_headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        # Try to update organization
        response = await async_client.patch(
            f"/api/v1/organizations/{test_organization.id}",
            json={"name": "Hacked Name"},
            headers=viewer_headers,
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_organization(self, async_client: AsyncClient, test_user: User, test_organization: Organization):
        """Test deleting organization (soft delete)."""
        from app.core.security import create_token_pair
        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        response = await async_client.delete(
            f"/api/v1/organizations/{test_organization.id}",
            headers=headers,
        )
        assert response.status_code == 204

        # Verify organization is deleted
        response = await async_client.get(
            f"/api/v1/organizations/{test_organization.id}",
            headers=headers,
        )
        assert response.status_code == 404


class TestMembershipEndpoints:
    """Tests for organization membership API endpoints."""

    @pytest.mark.asyncio
    async def test_invite_member(self, async_client: AsyncClient, test_user: User, test_organization: Organization):
        """Test inviting a member to organization."""
        from app.core.security import create_token_pair

        # Create user to invite using separate session
        TestingSessionLocal, test_engine = get_test_session()
        async with TestingSessionLocal() as session:
            invitee = User(
                email="invitee@example.com",
                username="invitee",
                hashed_password=get_password_hash("password123"),
                status=UserStatus.ACTIVE,
                email_verified=True,
            )
            session.add(invitee)
            await session.commit()
        await test_engine.dispose()

        # Use test_user (owner) for authentication
        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        response = await async_client.post(
            f"/api/v1/organizations/{test_organization.id}/members",
            json={
                "email": "invitee@example.com",
                "role_name": "developer",
            },
            headers=headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["user_email"] == "invitee@example.com"
        assert data["role_name"] == "developer"
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_invite_member_not_admin(self, async_client: AsyncClient, test_organization: Organization):
        """Test inviting member without admin permission fails."""
        # Create users using separate session
        TestingSessionLocal, test_engine = get_test_session()
        async with TestingSessionLocal() as session:
            viewer_user = User(
                email="viewer2@example.com",
                username="viewer2",
                hashed_password=get_password_hash("password123"),
                status=UserStatus.ACTIVE,
                email_verified=True,
            )
            invitee_user = User(
                email="invitee2@example.com",
                username="invitee2",
                hashed_password=get_password_hash("password123"),
                status=UserStatus.ACTIVE,
                email_verified=True,
            )
            session.add_all([viewer_user, invitee_user])
            await session.flush()

            # Get viewer role
            viewer_role = await session.execute(
                select(Role).where(Role.name == "viewer")
            )
            viewer_role = viewer_role.scalar_one()

            # Add viewer as member
            viewer_member = OrganizationMember(
                organization_id=test_organization.id,
                user_id=viewer_user.id,
                role_id=viewer_role.id,
                role_name=MemberRole.VIEWER,
                is_active=True,
            )
            session.add(viewer_member)
            await session.commit()
        await test_engine.dispose()

        # Login as viewer
        login_response = await async_client.post(
            "/api/v1/auth/login",
            json={"username": "viewer2", "password": "password123"},
        )
        tokens = login_response.json()
        viewer_headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        # Try to invite
        response = await async_client.post(
            f"/api/v1/organizations/{test_organization.id}/members",
            json={
                "email": "invitee2@example.com",
                "role_name": "developer",
            },
            headers=viewer_headers,
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_invite_nonexistent_user(self, async_client: AsyncClient, test_user: User, test_organization: Organization):
        """Test inviting nonexistent user fails."""
        from app.core.security import create_token_pair
        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        response = await async_client.post(
            f"/api/v1/organizations/{test_organization.id}/members",
            json={
                "email": "nonexistent@example.com",
                "role_name": "developer",
            },
            headers=headers,
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_invite_already_member(self, async_client: AsyncClient, test_user: User, test_organization: Organization):
        """Test inviting already member fails."""
        from app.core.security import create_token_pair
        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        response = await async_client.post(
            f"/api/v1/organizations/{test_organization.id}/members",
            json={
                "email": test_user.email,
                "role_name": "developer",
            },
            headers=headers,
        )
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_invite_invalid_role(self, async_client: AsyncClient, test_user: User, test_organization: Organization):
        """Test inviting with invalid role fails."""
        from app.core.security import create_token_pair
        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        response = await async_client.post(
            f"/api/v1/organizations/{test_organization.id}/members",
            json={
                "email": "some@example.com",
                "role_name": "invalid_role",
            },
            headers=headers,
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_members(self, async_client: AsyncClient, test_user: User, test_organization: Organization):
        """Test listing organization members."""
        from app.core.security import create_token_pair
        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        response = await async_client.get(
            f"/api/v1/organizations/{test_organization.id}/members",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        # Owner should be in list
        owner = next((m for m in data if m["role_name"] == "owner"), None)
        assert owner is not None

    @pytest.mark.asyncio
    async def test_update_member_role(self, async_client: AsyncClient, test_user: User, test_organization: Organization):
        """Test updating member role."""
        from app.core.security import create_token_pair
        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        # Create and invite a member first
        TestingSessionLocal, test_engine = get_test_session()
        async with TestingSessionLocal() as session:
            invitee = User(
                email="member@example.com",
                username="member",
                hashed_password=get_password_hash("password123"),
                status=UserStatus.ACTIVE,
                email_verified=True,
            )
            session.add(invitee)
            await session.commit()
        await test_engine.dispose()

        invite_response = await async_client.post(
            f"/api/v1/organizations/{test_organization.id}/members",
            json={
                "email": "member@example.com",
                "role_name": "viewer",
            },
            headers=headers,
        )
        member_id = invite_response.json()["id"]

        # Update member role
        response = await async_client.patch(
            f"/api/v1/organizations/{test_organization.id}/members/{member_id}",
            json={"role_name": "developer"},
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["role_name"] == "developer"

    @pytest.mark.asyncio
    async def test_update_member_not_owner(self, async_client: AsyncClient, test_organization: Organization):
        """Test updating member without owner permission fails."""
        # Create users using separate session
        TestingSessionLocal, test_engine = get_test_session()
        async with TestingSessionLocal() as session:
            admin_user = User(
                email="admin2@example.com",
                username="admin2",
                hashed_password=get_password_hash("password123"),
                status=UserStatus.ACTIVE,
                email_verified=True,
            )
            session.add(admin_user)
            await session.flush()

            # Get admin role
            admin_role = await session.execute(
                select(Role).where(Role.name == "administrator")
            )
            admin_role = admin_role.scalar_one()

            # Add as admin
            admin_member = OrganizationMember(
                organization_id=test_organization.id,
                user_id=admin_user.id,
                role_id=admin_role.id,
                role_name=MemberRole.ADMINISTRATOR,
                is_active=True,
            )
            session.add(admin_member)

            # Create another member to update
            member_user = User(
                email="member2@example.com",
                username="member2",
                hashed_password=get_password_hash("password123"),
                status=UserStatus.ACTIVE,
                email_verified=True,
            )
            session.add(member_user)
            await session.flush()

            viewer_role = await session.execute(
                select(Role).where(Role.name == "viewer")
            )
            viewer_role = viewer_role.scalar_one()

            member = OrganizationMember(
                organization_id=test_organization.id,
                user_id=member_user.id,
                role_id=viewer_role.id,
                role_name=MemberRole.VIEWER,
                is_active=True,
            )
            session.add(member)
            await session.commit()
            member_id = member.id
        await test_engine.dispose()

        # Login as admin
        login_response = await async_client.post(
            "/api/v1/auth/login",
            json={"username": "admin2", "password": "password123"},
        )
        tokens = login_response.json()
        admin_headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        # Try to update member (admin cannot update, only owner)
        response = await async_client.patch(
            f"/api/v1/organizations/{test_organization.id}/members/{member_id}",
            json={"role_name": "developer"},
            headers=admin_headers,
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_remove_member(self, async_client: AsyncClient, test_user: User, test_organization: Organization):
        """Test removing member from organization."""
        from app.core.security import create_token_pair
        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        # Create and invite a member first
        TestingSessionLocal, test_engine = get_test_session()
        async with TestingSessionLocal() as session:
            invitee = User(
                email="toremove@example.com",
                username="toremove",
                hashed_password=get_password_hash("password123"),
                status=UserStatus.ACTIVE,
                email_verified=True,
            )
            session.add(invitee)
            await session.commit()
        await test_engine.dispose()

        invite_response = await async_client.post(
            f"/api/v1/organizations/{test_organization.id}/members",
            json={
                "email": "toremove@example.com",
                "role_name": "viewer",
            },
            headers=headers,
        )
        member_id = invite_response.json()["id"]

        # Remove member
        response = await async_client.delete(
            f"/api/v1/organizations/{test_organization.id}/members/{member_id}",
            headers=headers,
        )
        assert response.status_code == 204

        # Verify member is removed
        list_response = await async_client.get(
            f"/api/v1/organizations/{test_organization.id}/members",
            headers=headers,
        )
        members = list_response.json()
        assert not any(m["id"] == member_id for m in members)

    @pytest.mark.asyncio
    async def test_remove_member_not_owner(self, async_client: AsyncClient, test_organization: Organization):
        """Test removing member without owner permission fails."""
        # Create users using separate session
        TestingSessionLocal, test_engine = get_test_session()
        async with TestingSessionLocal() as session:
            admin_user = User(
                email="admin3@example.com",
                username="admin3",
                hashed_password=get_password_hash("password123"),
                status=UserStatus.ACTIVE,
                email_verified=True,
            )
            session.add(admin_user)
            await session.flush()

            admin_role = await session.execute(
                select(Role).where(Role.name == "administrator")
            )
            admin_role = admin_role.scalar_one()

            admin_member = OrganizationMember(
                organization_id=test_organization.id,
                user_id=admin_user.id,
                role_id=admin_role.id,
                role_name=MemberRole.ADMINISTRATOR,
                is_active=True,
            )
            session.add(admin_member)

            # Create member to remove
            member_user = User(
                email="member3@example.com",
                username="member3",
                hashed_password=get_password_hash("password123"),
                status=UserStatus.ACTIVE,
                email_verified=True,
            )
            session.add(member_user)
            await session.flush()

            viewer_role = await session.execute(
                select(Role).where(Role.name == "viewer")
            )
            viewer_role = viewer_role.scalar_one()

            member = OrganizationMember(
                organization_id=test_organization.id,
                user_id=member_user.id,
                role_id=viewer_role.id,
                role_name=MemberRole.VIEWER,
                is_active=True,
            )
            session.add(member)
            await session.commit()
            member_id = member.id
        await test_engine.dispose()

        # Login as admin
        login_response = await async_client.post(
            "/api/v1/auth/login",
            json={"username": "admin3", "password": "password123"},
        )
        tokens = login_response.json()
        admin_headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        # Try to remove member (admin cannot remove)
        response = await async_client.delete(
            f"/api/v1/organizations/{test_organization.id}/members/{member_id}",
            headers=admin_headers,
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_owner_cannot_remove_self(self, async_client: AsyncClient, test_user: User, test_organization: Organization):
        """Test owner cannot remove themselves."""
        from app.core.security import create_token_pair
        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        # Get owner's member ID
        list_response = await async_client.get(
            f"/api/v1/organizations/{test_organization.id}/members",
            headers=headers,
        )
        owner_member = next(m for m in list_response.json() if m["role_name"] == "owner")

        # Try to remove self
        response = await async_client.delete(
            f"/api/v1/organizations/{test_organization.id}/members/{owner_member['id']}",
            headers=headers,
        )
        assert response.status_code == 400