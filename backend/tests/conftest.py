"""
StateFlow Test Configuration

Pytest fixtures and configuration for testing.
"""
import asyncio
import os
from typing import AsyncGenerator, Generator
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

# Set test environment BEFORE importing app modules
os.environ["ENVIRONMENT"] = "testing"
# Allow DATABASE_URL to be overridden by environment (e.g., in Docker)
if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://stateflow:stateflow_dev_password@localhost:5433/stateflow"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
os.environ["REFRESH_TOKEN_EXPIRE_DAYS"] = "7"
os.environ["BCRYPT_ROUNDS"] = "1"

from app.core.database import Base, get_session
from app.core.security import get_password_hash
from app.main import create_app
from app.models.organization import Organization, OrganizationMember, MemberRole, OrganizationStatus
from app.models.user import User, UserStatus, Role, Permission, RefreshToken
from app.models.workflow import Workflow, WorkflowStatus


# Test database engine (async) - session scoped
TEST_DATABASE_URL = os.environ["DATABASE_URL"]
test_engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
TestingSessionLocal = sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)

print("CONFTEST: Module loaded, fixtures defined")


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
async def setup_database() -> AsyncGenerator[None, None]:
    """Create database tables once per test session."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function", autouse=True)
async def _clean_db_per_test() -> AsyncGenerator[None, None]:
    """Clean database tables after each test to ensure isolation.

    This is needed because the client fixture creates new sessions that commit
    transactions, persisting data between tests.
    """
    yield
    # Create a new session for cleanup to avoid transaction conflicts
    async with TestingSessionLocal() as session:
        from sqlalchemy import text
        await session.execute(text("""
            TRUNCATE TABLE
                users,
                organizations,
                organization_members,
                roles,
                permissions,
                workflows,
                workflow_versions,
                workflow_steps,
                workflow_executions,
                step_executions,
                compensation_executions,
                execution_events,
                idempotency_records,
                outbox_events,
                worker_heartbeats,
                audit_logs,
                refresh_tokens
            RESTART IDENTITY CASCADE
        """))
        await session.commit()


@pytest_asyncio.fixture(scope="function", loop_scope="function")
async def db_session(setup_database) -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test with transaction rollback."""
    async with TestingSessionLocal() as session:
        # Begin a transaction that will be rolled back at the end of the test
        trans = await session.begin()
        # Attach transaction to session for test fixtures that need to commit
        session._test_trans = trans
        try:
            yield session
        finally:
            # Rollback the outer transaction if still active
            if trans.is_active:
                await trans.rollback()
            await session.close()


@pytest.fixture(scope="function")
def client() -> Generator[TestClient, None, None]:
    """Create a synchronous test client with a new database session per request."""
    # Create a new session for each request to avoid event loop conflicts
    # between the TestClient's thread pool and the test's event loop.
    # Clean up database after each request to ensure test isolation.
    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with TestingSessionLocal() as session:
            yield session
            # After request, expire all objects to avoid stale data
            await session.close()

    app = create_app()
    app.dependency_overrides[get_session] = override_get_session

    print("DEBUG client: Creating TestClient")
    test_client = TestClient(app)
    print("DEBUG client: TestClient created, running lifespan startup")
    test_client.__enter__()
    print("DEBUG client: Lifespan startup complete")
    try:
        yield test_client
    finally:
        print("DEBUG client: Running lifespan shutdown")
        test_client.__exit__(None, None, None)
        print("DEBUG client: Lifespan shutdown complete")

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def async_client(db_session: AsyncSession) -> Generator[AsyncClient, None, None]:
    """Create an async test client with overridden database session."""
    def override_get_session():
        yield db_session

    app = create_app()
    app.dependency_overrides[get_session] = override_get_session

    # Use synchronous context manager for AsyncClient
    import httpx
    transport = httpx.ASGITransport(app=app)
    ac = AsyncClient(transport=transport, base_url="http://test")
    try:
        yield ac
    finally:
        # Don't await close here - let pytest handle it
        pass

    app.dependency_overrides.clear()


import uuid

# ... (keep the existing imports)


@pytest_asyncio.fixture(scope="function", loop_scope="function")
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user by committing the db_session's transaction."""
    # Use unique email/username per test to avoid conflicts
    unique_id = uuid.uuid4().hex[:8]
    user = User(
        email=f"test_{unique_id}@example.com",
        username=f"testuser_{unique_id}",
        hashed_password=get_password_hash("password123"),
        full_name="Test User",
        status=UserStatus.ACTIVE,
        email_verified=True,
    )
    db_session.add(user)
    # Commit the outer transaction to make user visible to other sessions
    await db_session._test_trans.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function", loop_scope="function")
async def test_superuser(db_session: AsyncSession) -> User:
    """Create a test superuser by committing the db_session's transaction."""
    unique_id = uuid.uuid4().hex[:8]
    user = User(
        email=f"admin_{unique_id}@example.com",
        username=f"admin_{unique_id}",
        hashed_password=get_password_hash("password123"),
        full_name="Admin User",
        status=UserStatus.ACTIVE,
        email_verified=True,
        is_superuser=True,
    )
    db_session.add(user)
    await db_session._test_trans.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function", loop_scope="function")
async def test_organization(test_user: User) -> Organization:
    """Create a test organization with owner."""
    async with TestingSessionLocal() as session:
        # Use unique slug based on test_user's username
        unique_slug = f"test-org-{test_user.username.split('_')[-1]}"
        org = Organization(
            name="Test Organization",
            slug=unique_slug,
            description="Test organization",
            status=OrganizationStatus.ACTIVE,
        )
        session.add(org)
        await session.flush()

        # Create roles if not exist
        from sqlalchemy import select
        result = await session.execute(select(Role).where(Role.name == "owner"))
        owner_role = result.scalar_one_or_none()
        if not owner_role:
            owner_role = Role(name="owner", display_name="Owner", description="Organization owner", is_system=True)
            admin_role = Role(name="administrator", display_name="Administrator", description="Organization administrator", is_system=True)
            dev_role = Role(name="developer", display_name="Developer", description="Organization developer", is_system=True)
            viewer_role = Role(name="viewer", display_name="Viewer", description="Organization viewer", is_system=True)
            session.add_all([owner_role, admin_role, dev_role, viewer_role])
            await session.flush()

        # Add creator as owner
        member = OrganizationMember(
            organization_id=org.id,
            user_id=test_user.id,
            role_id=owner_role.id,
            role_name=MemberRole.OWNER,
            is_active=True,
        )
        session.add(member)
        await session.commit()
        await session.refresh(org)
        await session.close()
        return org


@pytest.fixture
def auth_headers(client: TestClient) -> dict:
    """Get authentication headers for test user."""
    # Register and login a user
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "authuser@example.com",
            "username": "authuser",
            "password": "password123",
        },
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "authuser", "password": "password123"},
    )
    assert response.status_code == 200
    tokens = response.json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
def org_auth_headers(client: TestClient, test_organization: Organization) -> dict:
    """Get authentication headers with organization context."""
    # Register and login a user
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "orgauth@example.com",
            "username": "orgauthuser",
            "password": "password123",
        },
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "orgauthuser", "password": "password123"},
    )
    assert response.status_code == 200
    tokens = response.json()
    return {
        "Authorization": f"Bearer {tokens['access_token']}",
        "X-Organization-ID": str(test_organization.id),
    }


@pytest_asyncio.fixture(scope="function", loop_scope="function")
async def test_workflow(test_organization: Organization, test_user: User) -> Workflow:
    """Create a test workflow."""
    async with TestingSessionLocal() as session:
        workflow = Workflow(
            name="Test Workflow",
            description="A test workflow",
            organization_id=test_organization.id,
            status=WorkflowStatus.DRAFT,
            current_version=1,
            created_by=test_user.id,
        )
        session.add(workflow)
        await session.commit()
        await session.refresh(workflow)
        await session.close()
        return workflow


@pytest_asyncio.fixture(scope="function", loop_scope="function")
async def create_test_user() -> User:
    """Create a test user in a separate session for testing."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import NullPool
    from app.core.config import settings

    test_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    TestingSessionLocal = sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestingSessionLocal() as session:
        unique_id = uuid.uuid4().hex[:8]
        user = User(
            email=f"testuser_{unique_id}@example.com",
            username=f"testuser_{unique_id}",
            hashed_password=get_password_hash("password123"),
            status=UserStatus.ACTIVE,
            email_verified=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id
        user_email = user.email
        user_username = user.username

    await test_engine.dispose()

    # Return a simple object with the needed attributes
    class TestUserData:
        def __init__(self, id, email, username):
            self.id = id
            self.email = email
            self.username = username

    return TestUserData(user_id, user_email, user_username)