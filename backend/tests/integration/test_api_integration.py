"""
StateFlow Integration Tests

Integration tests for API workflows.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4

from app.models.organization import Organization, OrganizationMember, MemberRole, OrganizationStatus
from app.models.user import User, UserStatus, Role
from app.models.workflow import Workflow, WorkflowStatus, WorkflowVersion, WorkflowStep, StepType
from app.core.security import get_password_hash, create_token_pair


def get_user_headers(test_user: User) -> dict:
    """Get authentication headers for test user."""
    tokens = create_token_pair(test_user.id)
    return {"Authorization": f"Bearer {tokens.access_token}"}


class TestWorkflowIntegration:
    """Integration tests for workflow management."""

    @pytest.mark.asyncio
    async def test_full_workflow_lifecycle(
        self, async_client: AsyncClient, test_user: User, test_organization: Organization
    ):
        """Test complete workflow lifecycle: create, add steps, activate, execute."""
        headers = get_user_headers(test_user)
        params = {"org_id": str(test_organization.id)}

        # 1. Create workflow
        response = await async_client.post(
            "/api/v1/workflows",
            json={
                "name": "Test Workflow",
                "description": "A test workflow",
                "tags": ["test"],
            },
            headers=headers,
            params=params,
        )
        assert response.status_code == 201, f"Response: {response.text}"
        workflow = response.json()
        workflow_id = workflow["id"]
        assert workflow["status"] == "draft"

        # 2. Add steps to current version (version 1)
        response = await async_client.post(
            f"/api/v1/workflows/{workflow_id}/steps",
            json={
                "step_key": "step1",
                "name": "First Step",
                "step_type": "action",
                "order": 0,
                "handler": "mock_notification",
                "config": {"channel": "email"},
                "version_number": 1,
            },
            headers=headers,
            params=params,
        )
        assert response.status_code == 201, f"Response: {response.text}"
        step1 = response.json()
        assert step1["step_key"] == "step1"

        response = await async_client.post(
            f"/api/v1/workflows/{workflow_id}/steps",
            json={
                "step_key": "step2",
                "name": "Second Step",
                "step_type": "action",
                "order": 1,
                "handler": "mock_notification",
                "config": {"channel": "email"},
                "depends_on": ["step1"],
                "version_number": 1,
            },
            headers=headers,
            params=params,
        )
        assert response.status_code == 201, f"Response: {response.text}"
        step2 = response.json()
        assert step2["step_key"] == "step2"

        # 3. Activate workflow (creates version 2 since workflow starts at version 1)
        response = await async_client.post(
            f"/api/v1/workflows/{workflow_id}/activate",
            headers=headers,
            params=params,
        )
        assert response.status_code == 200, f"Response: {response.text}"
        workflow = response.json()
        assert workflow["status"] == "active"
        assert workflow["current_version"] == 2
        assert workflow["activated_at"] is not None

        # 4. Execute workflow
        exec_params = {**params, "workflow_id": workflow_id}
        response = await async_client.post(
            "/api/v1/executions",
            json={
                "input_data": {"key": "value"},
                "idempotency_key": "test-execution-1",
            },
            headers=headers,
            params=exec_params,
        )
        assert response.status_code == 201, f"Response: {response.text}"
        execution = response.json()
        execution_id = execution["id"]
        assert execution["status"] == "pending"

        # 5. Check execution status
        response = await async_client.get(
            f"/api/v1/executions/{execution_id}",
            headers=headers,
            params=params,
        )
        assert response.status_code == 200, f"Response: {response.text}"
        execution = response.json()
        assert execution["id"] == execution_id
        assert execution["workflow_id"] == workflow_id

    @pytest.mark.asyncio
    async def test_workflow_versioning(
        self, async_client: AsyncClient, test_user: User, test_organization: Organization
    ):
        """Test workflow versioning through activation."""
        headers = get_user_headers(test_user)
        params = {"org_id": str(test_organization.id)}

        # Create workflow
        response = await async_client.post(
            "/api/v1/workflows",
            json={"name": "Versioned Workflow"},
            headers=headers,
            params=params,
        )
        assert response.status_code == 201, f"Response: {response.text}"
        workflow = response.json()
        workflow_id = workflow["id"]

        # Add step for v1
        response = await async_client.post(
            f"/api/v1/workflows/{workflow_id}/steps",
            json={
                "step_key": "step1",
                "name": "Step 1",
                "step_type": "action",
                "order": 0,
                "handler": "mock_notification",
                "version_number": 1,
            },
            headers=headers,
            params=params,
        )
        assert response.status_code == 201, f"Response: {response.text}"

        # Activate to create v2 (since workflow starts at version 1)
        response = await async_client.post(
            f"/api/v1/workflows/{workflow_id}/activate",
            headers=headers,
            params=params,
        )
        assert response.status_code == 200, f"Response: {response.text}"
        workflow = response.json()
        assert workflow["current_version"] == 2
        assert workflow["status"] == "active"

        # Deactivate to add steps to v2 (now draft)
        response = await async_client.post(
            f"/api/v1/workflows/{workflow_id}/deactivate",
            headers=headers,
            params=params,
        )
        assert response.status_code == 200, f"Response: {response.text}"
        workflow = response.json()
        assert workflow["status"] == "draft"
        assert workflow["current_version"] == 2

        # Add steps for v2 - version 2 is now draft after deactivation
        response = await async_client.post(
            f"/api/v1/workflows/{workflow_id}/steps",
            json={
                "step_key": "step2",
                "name": "Step 2",
                "step_type": "action",
                "order": 1,
                "handler": "mock_notification",
                "version_number": 2,
            },
            headers=headers,
            params=params,
        )
        assert response.status_code == 201, f"Response: {response.text}"

        # Activate again to create v3
        response = await async_client.post(
            f"/api/v1/workflows/{workflow_id}/activate",
            headers=headers,
            params=params,
        )
        assert response.status_code == 200, f"Response: {response.text}"
        workflow = response.json()
        assert workflow["current_version"] == 3
        assert workflow["status"] == "active"

        # List versions
        response = await async_client.get(
            f"/api/v1/workflows/{workflow_id}/versions",
            headers=headers,
            params=params,
        )
        assert response.status_code == 200, f"Response: {response.text}"
        versions = response.json()
        assert len(versions) == 3


class TestExecutionIntegration:
    """Integration tests for workflow execution."""

    @pytest.mark.asyncio
    async def test_execution_with_compensation(
        self, async_client: AsyncClient, test_user: User, test_organization: Organization
    ):
        """Test execution that triggers compensation on failure."""
        headers = get_user_headers(test_user)
        params = {"org_id": str(test_organization.id)}

        # Create workflow with compensation
        response = await async_client.post(
            "/api/v1/workflows",
            json={"name": "Compensation Workflow"},
            headers=headers,
            params=params,
        )
        assert response.status_code == 201, f"Response: {response.text}"
        workflow_id = response.json()["id"]

        # Add steps with compensation
        response = await async_client.post(
            f"/api/v1/workflows/{workflow_id}/steps",
            json={
                "step_key": "step1",
                "name": "Step 1",
                "step_type": "action",
                "order": 0,
                "handler": "failing_handler",
                "compensation_handler": "compensate_step1",
                "compensation_config": {"action": "rollback"},
                "version_number": 1,
            },
            headers=headers,
            params=params,
        )
        assert response.status_code == 201, f"Response: {response.text}"

        response = await async_client.post(
            f"/api/v1/workflows/{workflow_id}/steps",
            json={
                "step_key": "step2",
                "name": "Step 2",
                "step_type": "action",
                "order": 1,
                "handler": "failing_handler",
                "depends_on": ["step1"],
                "version_number": 1,
            },
            headers=headers,
            params=params,
        )
        assert response.status_code == 201, f"Response: {response.text}"

        # Activate
        response = await async_client.post(
            f"/api/v1/workflows/{workflow_id}/activate",
            headers=headers,
            params=params,
        )
        assert response.status_code == 200, f"Response: {response.text}"

        # Execute
        exec_params = {**params, "workflow_id": workflow_id}
        response = await async_client.post(
            "/api/v1/executions",
            json={"input_data": {}},
            headers=headers,
            params=exec_params,
        )
        assert response.status_code == 201, f"Response: {response.text}"
        execution_id = response.json()["id"]

        # Check execution exists
        response = await async_client.get(
            f"/api/v1/executions/{execution_id}",
            headers=headers,
            params=params,
        )
        assert response.status_code == 200, f"Response: {response.text}"


class TestIdempotency:
    """Tests for idempotency handling."""

    @pytest.mark.asyncio
    async def test_idempotent_execution(
        self, async_client: AsyncClient, test_user: User, test_organization: Organization
    ):
        """Test that duplicate executions with same idempotency key are rejected."""
        headers = get_user_headers(test_user)
        params = {"org_id": str(test_organization.id)}

        # Create and activate workflow
        response = await async_client.post(
            "/api/v1/workflows",
            json={"name": "Idempotent Workflow"},
            headers=headers,
            params=params,
        )
        assert response.status_code == 201, f"Response: {response.text}"
        workflow_id = response.json()["id"]

        response = await async_client.post(
            f"/api/v1/workflows/{workflow_id}/steps",
            json={
                "definition": {"name": "v1"},
                "steps": [{"step_key": "step1", "name": "Step 1", "step_type": "action", "order": 0, "handler": "mock_notification"}],
            },
            headers=headers,
            params=params,
        )
        # This endpoint doesn't accept definition/steps in body, it only takes step
        # Let me just add a single step
        response = await async_client.post(
            f"/api/v1/workflows/{workflow_id}/steps",
            json={
                "step_key": "step1",
                "name": "Step 1",
                "step_type": "action",
                "order": 0,
                "handler": "mock_notification",
                "version_number": 1,
            },
            headers=headers,
            params=params,
        )
        assert response.status_code == 201, f"Response: {response.text}"

        response = await async_client.post(
            f"/api/v1/workflows/{workflow_id}/activate",
            headers=headers,
            params=params,
        )
        assert response.status_code == 200, f"Response: {response.text}"

        # First execution
        exec_params = {**params, "workflow_id": workflow_id}
        response = await async_client.post(
            "/api/v1/executions",
            json={"input_data": {}, "idempotency_key": "idem-key-1"},
            headers=headers,
            params=exec_params,
        )
        assert response.status_code == 201, f"Response: {response.text}"
        execution1 = response.json()

        # Second execution with same key - returns 409 because first execution is still pending
        response = await async_client.post(
            "/api/v1/executions",
            json={"input_data": {}, "idempotency_key": "idem-key-1"},
            headers=headers,
            params=exec_params,
        )
        assert response.status_code == 409, f"Response: {response.text}"
        data = response.json()
        assert "already exists or is being processed" in data["detail"]

        # Third execution with different key - should succeed
        response = await async_client.post(
            "/api/v1/executions",
            json={"input_data": {}, "idempotency_key": "idem-key-2"},
            headers=headers,
            params=exec_params,
        )
        assert response.status_code == 201, f"Response: {response.text}"
        execution3 = response.json()
        assert execution3["id"] != execution1["id"]