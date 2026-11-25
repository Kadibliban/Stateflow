"""
StateFlow Workflow Tests

Unit tests for workflow CRUD, versioning, steps, and validation.
"""
import pytest
from datetime import datetime, timezone
from uuid import uuid4

from app.models.workflow import (
    Workflow,
    WorkflowVersion,
    WorkflowStep,
    WorkflowStatus,
    StepType,
    RetryPolicy,
)
from app.models.organization import Organization, OrganizationMember, MemberRole, OrganizationStatus
from app.models.user import User, UserStatus, Role
from app.core.security import get_password_hash


class TestWorkflowEndpoints:
    """Tests for workflow API endpoints."""

    @pytest.mark.asyncio
    async def test_create_workflow(self, client, test_user, test_organization):
        """Test creating a workflow."""
        from app.core.security import create_token_pair
        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        response = client.post(
            "/api/v1/workflows",
            json={
                "name": "Test Workflow",
                "description": "A test workflow",
                "tags": ["test", "demo"],
            },
            headers=headers,
            params={"org_id": str(test_organization.id)},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Workflow"
        assert data["description"] == "A test workflow"
        assert data["tags"] == ["test", "demo"]
        assert data["status"] == "draft"
        assert data["current_version"] == 1

    @pytest.mark.asyncio
    async def test_create_workflow_duplicate_name(self, client, test_user, test_organization, test_workflow):
        """Test creating workflow with duplicate name fails."""
        from app.core.security import create_token_pair
        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        response = client.post(
            "/api/v1/workflows",
            json={
                "name": test_workflow.name,
                "description": "Another workflow",
            },
            headers=headers,
            params={"org_id": str(test_organization.id)},
        )
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_list_workflows(self, client, test_user, test_organization, test_workflow):
        """Test listing workflows in organization."""
        from app.core.security import create_token_pair
        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        response = client.get(
            "/api/v1/workflows",
            headers=headers,
            params={"org_id": str(test_organization.id)},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        workflow_names = [w["name"] for w in data]
        assert test_workflow.name in workflow_names

    @pytest.mark.asyncio
    async def test_get_workflow(self, client, test_user, test_organization, test_workflow):
        """Test getting workflow by ID."""
        from app.core.security import create_token_pair
        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        response = client.get(
            f"/api/v1/workflows/{test_workflow.id}",
            headers=headers,
            params={"org_id": str(test_organization.id)},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_workflow.id)
        assert data["name"] == test_workflow.name

    @pytest.mark.asyncio
    async def test_update_workflow(self, client, test_user, test_organization, test_workflow):
        """Test updating workflow (draft only)."""
        from app.core.security import create_token_pair
        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        response = client.patch(
            f"/api/v1/workflows/{test_workflow.id}",
            json={
                "name": "Updated Workflow",
                "description": "Updated description",
            },
            headers=headers,
            params={"org_id": str(test_organization.id)},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Workflow"
        assert data["description"] == "Updated description"

    @pytest.mark.asyncio
    async def test_update_workflow_not_active(self, client, test_user, test_organization, test_workflow, db_session):
        """Test updating active workflow fails."""
        from app.core.security import create_token_pair
        from sqlalchemy import select
        from app.models.workflow import Workflow
        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        # Activate workflow first - re-query in db_session to ensure it's tracked
        result = await db_session.execute(select(Workflow).where(Workflow.id == test_workflow.id))
        workflow = result.scalar_one()
        workflow.status = WorkflowStatus.ACTIVE
        await db_session.commit()

        response = client.patch(
            f"/api/v1/workflows/{test_workflow.id}",
            json={"name": "Should Fail"},
            headers=headers,
            params={"org_id": str(test_organization.id)},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_delete_workflow(self, client, test_user, test_organization, test_workflow):
        """Test deleting workflow (not active)."""
        from app.core.security import create_token_pair
        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        response = client.delete(
            f"/api/v1/workflows/{test_workflow.id}",
            headers=headers,
            params={"org_id": str(test_organization.id)},
        )
        assert response.status_code == 204

        # Verify workflow is deleted
        response = client.get(
            f"/api/v1/workflows/{test_workflow.id}",
            headers=headers,
            params={"org_id": str(test_organization.id)},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_active_workflow_fails(self, client, test_user, test_organization, test_workflow, db_session):
        """Test deleting active workflow fails."""
        from app.core.security import create_token_pair
        from sqlalchemy import select
        from app.models.workflow import Workflow
        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        # Activate workflow first - re-query in db_session to ensure it's tracked
        result = await db_session.execute(select(Workflow).where(Workflow.id == test_workflow.id))
        workflow = result.scalar_one()
        workflow.status = WorkflowStatus.ACTIVE
        await db_session.commit()

        response = client.delete(
            f"/api/v1/workflows/{test_workflow.id}",
            headers=headers,
            params={"org_id": str(test_organization.id)},
        )
        assert response.status_code == 400


class TestWorkflowActivation:
    """Tests for workflow activation/deactivation."""

    @pytest.mark.asyncio
    async def test_activate_workflow(self, client, test_user, test_organization, test_workflow, db_session):
        """Test activating a workflow with steps."""
        from app.core.security import create_token_pair
        from app.models.workflow import WorkflowVersion, WorkflowStep, StepType
        from sqlalchemy import select

        # Add a step to the workflow first
        result = await db_session.execute(
            select(WorkflowVersion).where(
                WorkflowVersion.workflow_id == test_workflow.id,
                WorkflowVersion.version_number == 1
            )
        )
        version = result.scalar_one_or_none()
        if not version:
            version = WorkflowVersion(
                workflow_id=test_workflow.id,
                version_number=1,
                definition={},
                steps=[],
                connections=[],
                variables={},
                created_by=test_workflow.created_by,
            )
            db_session.add(version)
            await db_session.flush()

        step = WorkflowStep(
            version_id=version.id,
            step_key="step1",
            name="Step 1",
            step_type=StepType.ACTION,
            order=0,
            handler="mock_notification",
            config={},
        )
        db_session.add(step)
        await db_session.commit()

        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        response = client.post(
            f"/api/v1/workflows/{test_workflow.id}/activate",
            headers=headers,
            params={"org_id": str(test_organization.id)},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"
        assert data["current_version"] == 2
        assert data["activated_at"] is not None

    @pytest.mark.asyncio
    async def test_activate_workflow_no_steps_fails(self, client, test_user, test_organization, test_workflow):
        """Test activating workflow without steps fails."""
        from app.core.security import create_token_pair
        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        response = client.post(
            f"/api/v1/workflows/{test_workflow.id}/activate",
            headers=headers,
            params={"org_id": str(test_organization.id)},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_deactivate_workflow(self, client, test_user, test_organization, test_workflow, db_session):
        """Test deactivating a workflow."""
        from app.core.security import create_token_pair
        from sqlalchemy import select
        from app.models.workflow import Workflow
        from datetime import datetime, timezone

        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        # Re-query workflow in db_session
        result = await db_session.execute(select(Workflow).where(Workflow.id == test_workflow.id))
        workflow = result.scalar_one()
        workflow.status = WorkflowStatus.ACTIVE
        workflow.activated_at = datetime.now(timezone.utc)
        workflow.current_version = 2
        await db_session.commit()

        response = client.post(
            f"/api/v1/workflows/{test_workflow.id}/deactivate",
            headers=headers,
            params={"org_id": str(test_organization.id)},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "draft"


class TestWorkflowVersions:
    """Tests for workflow version management."""

    @pytest.mark.asyncio
    async def test_list_versions(self, client, test_user, test_organization, test_workflow, db_session):
        """Test listing workflow versions."""
        from app.core.security import create_token_pair
        from app.models.workflow import WorkflowVersion

        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        # Create a version
        version = WorkflowVersion(
            workflow_id=test_workflow.id,
            version_number=1,
            definition={},
            steps=[],
            connections=[],
            variables={},
            created_by=test_workflow.created_by,
        )
        db_session.add(version)
        await db_session.commit()

        response = client.get(
            f"/api/v1/workflows/{test_workflow.id}/versions",
            headers=headers,
            params={"org_id": str(test_organization.id)},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["version_number"] == 1

    @pytest.mark.asyncio
    async def test_get_version(self, client, test_user, test_organization, test_workflow, db_session):
        """Test getting specific workflow version."""
        from app.core.security import create_token_pair
        from app.models.workflow import WorkflowVersion

        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        version = WorkflowVersion(
            workflow_id=test_workflow.id,
            version_number=1,
            definition={},
            steps=[],
            connections=[],
            variables={},
            created_by=test_workflow.created_by,
            changelog="Initial version",
        )
        db_session.add(version)
        await db_session.commit()

        response = client.get(
            f"/api/v1/workflows/{test_workflow.id}/versions/1",
            headers=headers,
            params={"org_id": str(test_organization.id)},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["version_number"] == 1
        assert data["changelog"] == "Initial version"


class TestWorkflowSteps:
    """Tests for workflow step management."""

    @pytest.mark.asyncio
    async def test_create_step(self, client, test_user, test_organization, test_workflow, db_session):
        """Test adding step to workflow version."""
        from app.core.security import create_token_pair
        from app.models.workflow import WorkflowVersion

        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        version = WorkflowVersion(
            workflow_id=test_workflow.id,
            version_number=1,
            definition={},
            steps=[],
            connections=[],
            variables={},
            created_by=test_workflow.created_by,
        )
        db_session.add(version)
        await db_session.commit()

        response = client.post(
            f"/api/v1/workflows/{test_workflow.id}/steps",
            json={
                "step_key": "step1",
                "name": "First Step",
                "step_type": "action",
                "handler": "mock_notification",
                "config": {"channel": "email"},
                "order": 0,
            },
            headers=headers,
            params={"org_id": str(test_organization.id), "version_number": 1},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["step_key"] == "step1"
        assert data["name"] == "First Step"
        assert data["handler"] == "mock_notification"

    @pytest.mark.asyncio
    async def test_create_step_duplicate_key(self, client, test_user, test_organization, test_workflow, db_session):
        """Test creating step with duplicate key fails."""
        from app.core.security import create_token_pair
        from app.models.workflow import WorkflowVersion, WorkflowStep

        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        version = WorkflowVersion(
            workflow_id=test_workflow.id,
            version_number=1,
            definition={},
            steps=[],
            connections=[],
            variables={},
            created_by=test_workflow.created_by,
        )
        db_session.add(version)
        await db_session.commit()

        step = WorkflowStep(
            version_id=version.id,
            step_key="step1",
            name="Step 1",
            step_type=StepType.ACTION,
            order=0,
            handler="mock_notification",
            config={},
        )
        db_session.add(step)
        await db_session.commit()

        response = client.post(
            f"/api/v1/workflows/{test_workflow.id}/steps",
            json={
                "step_key": "step1",
                "name": "Duplicate Step",
                "step_type": "action",
                "handler": "mock_notification",
            },
            headers=headers,
            params={"org_id": str(test_organization.id), "version_number": 1},
        )
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_create_step_invalid_retry_policy(self, client, test_user, test_organization, test_workflow, db_session):
        """Test creating step with invalid retry policy fails."""
        from app.core.security import create_token_pair
        from app.models.workflow import WorkflowVersion
        from uuid import uuid4

        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        version = WorkflowVersion(
            workflow_id=test_workflow.id,
            version_number=1,
            definition={},
            steps=[],
            connections=[],
            variables={},
            created_by=test_workflow.created_by,
        )
        db_session.add(version)
        await db_session.commit()

        response = client.post(
            f"/api/v1/workflows/{test_workflow.id}/steps",
            json={
                "step_key": "step1",
                "name": "Step 1",
                "step_type": "action",
                "handler": "mock_notification",
                "retry_policy_id": str(uuid4()),
            },
            headers=headers,
            params={"org_id": str(test_organization.id), "version_number": 1},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_list_steps(self, client, test_user, test_organization, test_workflow, db_session):
        """Test listing workflow steps."""
        from app.core.security import create_token_pair
        from app.models.workflow import WorkflowVersion, WorkflowStep

        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        version = WorkflowVersion(
            workflow_id=test_workflow.id,
            version_number=1,
            definition={},
            steps=[],
            connections=[],
            variables={},
            created_by=test_workflow.created_by,
        )
        db_session.add(version)
        await db_session.commit()

        step1 = WorkflowStep(
            version_id=version.id,
            step_key="step1",
            name="Step 1",
            step_type=StepType.ACTION,
            order=0,
            handler="mock_notification",
            config={},
        )
        step2 = WorkflowStep(
            version_id=version.id,
            step_key="step2",
            name="Step 2",
            step_type=StepType.ACTION,
            order=1,
            handler="mock_payment",
            config={},
        )
        db_session.add_all([step1, step2])
        await db_session.commit()

        response = client.get(
            f"/api/v1/workflows/{test_workflow.id}/steps",
            headers=headers,
            params={"org_id": str(test_organization.id), "version_number": 1},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["step_key"] == "step1"
        assert data[1]["step_key"] == "step2"

    @pytest.mark.asyncio
    async def test_update_step(self, client, test_user, test_organization, test_workflow, db_session):
        """Test updating a workflow step."""
        from app.core.security import create_token_pair
        from app.models.workflow import WorkflowVersion, WorkflowStep

        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        version = WorkflowVersion(
            workflow_id=test_workflow.id,
            version_number=1,
            definition={},
            steps=[],
            connections=[],
            variables={},
            created_by=test_workflow.created_by,
        )
        db_session.add(version)
        await db_session.commit()

        step = WorkflowStep(
            version_id=version.id,
            step_key="step1",
            name="Step 1",
            step_type=StepType.ACTION,
            order=0,
            handler="mock_notification",
            config={},
        )
        db_session.add(step)
        await db_session.commit()

        response = client.patch(
            f"/api/v1/workflows/{test_workflow.id}/steps/step1",
            json={
                "name": "Updated Step",
                "description": "Updated description",
                "config": {"channel": "sms"},
            },
            headers=headers,
            params={"org_id": str(test_organization.id), "version_number": 1},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Step"
        assert data["description"] == "Updated description"
        assert data["config"] == {"channel": "sms"}

    @pytest.mark.asyncio
    async def test_delete_step(self, client, test_user, test_organization, test_workflow, db_session):
        """Test deleting a workflow step."""
        from app.core.security import create_token_pair
        from app.models.workflow import WorkflowVersion, WorkflowStep

        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        version = WorkflowVersion(
            workflow_id=test_workflow.id,
            version_number=1,
            definition={},
            steps=[],
            connections=[],
            variables={},
            created_by=test_workflow.created_by,
        )
        db_session.add(version)
        await db_session.commit()

        step = WorkflowStep(
            version_id=version.id,
            step_key="step1",
            name="Step 1",
            step_type=StepType.ACTION,
            order=0,
            handler="mock_notification",
            config={},
        )
        db_session.add(step)
        await db_session.commit()

        response = client.delete(
            f"/api/v1/workflows/{test_workflow.id}/steps/step1",
            headers=headers,
            params={"org_id": str(test_organization.id), "version_number": 1},
        )
        assert response.status_code == 204

        # Verify step is deleted
        response = client.get(
            f"/api/v1/workflows/{test_workflow.id}/steps",
            headers=headers,
            params={"org_id": str(test_organization.id), "version_number": 1},
        )
        data = response.json()
        assert len(data) == 0

    @pytest.mark.asyncio
    async def test_delete_step_with_dependency_fails(self, client, test_user, test_organization, test_workflow, db_session):
        """Test deleting step that other steps depend on fails."""
        from app.core.security import create_token_pair
        from app.models.workflow import WorkflowVersion, WorkflowStep

        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        version = WorkflowVersion(
            workflow_id=test_workflow.id,
            version_number=1,
            definition={},
            steps=[],
            connections=[],
            variables={},
            created_by=test_workflow.created_by,
        )
        db_session.add(version)
        await db_session.commit()

        step1 = WorkflowStep(
            version_id=version.id,
            step_key="step1",
            name="Step 1",
            step_type=StepType.ACTION,
            order=0,
            handler="mock_notification",
            config={},
        )
        step2 = WorkflowStep(
            version_id=version.id,
            step_key="step2",
            name="Step 2",
            step_type=StepType.ACTION,
            order=1,
            handler="mock_payment",
            config={},
            depends_on=["step1"],
        )
        db_session.add_all([step1, step2])
        await db_session.commit()

        response = client.delete(
            f"/api/v1/workflows/{test_workflow.id}/steps/step1",
            headers=headers,
            params={"org_id": str(test_organization.id), "version_number": 1},
        )
        assert response.status_code == 400


class TestWorkflowValidation:
    """Tests for workflow validation."""

    @pytest.mark.asyncio
    async def test_validate_workflow_valid(self, client, test_user, test_organization, test_workflow, db_session):
        """Test validating a valid workflow."""
        from app.core.security import create_token_pair
        from app.models.workflow import WorkflowVersion, WorkflowStep

        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        version = WorkflowVersion(
            workflow_id=test_workflow.id,
            version_number=1,
            definition={},
            steps=[],
            connections=[],
            variables={},
            created_by=test_workflow.created_by,
        )
        db_session.add(version)
        await db_session.commit()

        step = WorkflowStep(
            version_id=version.id,
            step_key="step1",
            name="Step 1",
            step_type=StepType.ACTION,
            order=0,
            handler="mock_notification",
            config={},
        )
        db_session.add(step)
        await db_session.commit()

        response = client.post(
            f"/api/v1/workflows/{test_workflow.id}/validate",
            headers=headers,
            params={"org_id": str(test_organization.id)},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True

    @pytest.mark.asyncio
    async def test_validate_workflow_no_steps(self, client, test_user, test_organization, test_workflow, db_session):
        """Test validating workflow without steps fails."""
        from app.core.security import create_token_pair
        from app.models.workflow import WorkflowVersion

        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        # Create a version without steps
        version = WorkflowVersion(
            workflow_id=test_workflow.id,
            version_number=1,
            definition={},
            steps=[],
            connections=[],
            variables={},
            created_by=test_workflow.created_by,
        )
        db_session.add(version)
        await db_session.commit()

        response = client.post(
            f"/api/v1/workflows/{test_workflow.id}/validate",
            headers=headers,
            params={"org_id": str(test_organization.id)},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("at least one step" in error for error in data["errors"])


class TestWorkflowClone:
    """Tests for workflow cloning."""

    @pytest.mark.asyncio
    async def test_clone_workflow(self, client, test_user, test_organization, test_workflow, db_session):
        """Test cloning a workflow."""
        from app.core.security import create_token_pair
        from app.models.workflow import WorkflowVersion, WorkflowStep

        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        version = WorkflowVersion(
            workflow_id=test_workflow.id,
            version_number=1,
            definition={},
            steps=[],
            connections=[],
            variables={},
            created_by=test_workflow.created_by,
        )
        db_session.add(version)
        await db_session.commit()

        step = WorkflowStep(
            version_id=version.id,
            step_key="step1",
            name="Step 1",
            step_type=StepType.ACTION,
            order=0,
            handler="mock_notification",
            config={"channel": "email"},
        )
        db_session.add(step)
        await db_session.commit()

        response = client.post(
            f"/api/v1/workflows/{test_workflow.id}/clone",
            headers=headers,
            params={"org_id": str(test_organization.id), "name": "Cloned Workflow"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Cloned Workflow"
        assert data["status"] == "draft"
        assert data["current_version"] == 1

        # Verify steps were cloned
        response = client.get(
            f"/api/v1/workflows/{data['id']}/steps",
            headers=headers,
            params={"org_id": str(test_organization.id)},
        )
        assert response.status_code == 200
        steps = response.json()
        assert len(steps) == 1
        assert steps[0]["step_key"] == "step1"

    @pytest.mark.asyncio
    async def test_clone_workflow_duplicate_name(self, client, test_user, test_organization, test_workflow):
        """Test cloning workflow with duplicate name fails."""
        from app.core.security import create_token_pair
        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        response = client.post(
            f"/api/v1/workflows/{test_workflow.id}/clone",
            headers=headers,
            params={"org_id": str(test_organization.id), "name": test_workflow.name},
        )
        assert response.status_code == 409


class TestWorkflowExportImport:
    """Tests for workflow export/import."""

    @pytest.mark.asyncio
    async def test_export_workflow(self, client, test_user, test_organization, test_workflow, db_session):
        """Test exporting workflow definition."""
        from app.core.security import create_token_pair
        from app.models.workflow import WorkflowVersion, WorkflowStep

        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        version = WorkflowVersion(
            workflow_id=test_workflow.id,
            version_number=1,
            definition={},
            steps=[],
            connections=[],
            variables={},
            created_by=test_workflow.created_by,
        )
        db_session.add(version)
        await db_session.commit()

        step = WorkflowStep(
            version_id=version.id,
            step_key="step1",
            name="Step 1",
            step_type=StepType.ACTION,
            order=0,
            handler="mock_notification",
            config={"channel": "email"},
        )
        db_session.add(step)
        await db_session.commit()

        response = client.get(
            f"/api/v1/workflows/{test_workflow.id}/export",
            headers=headers,
            params={"org_id": str(test_organization.id)},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["workflow"]["name"] == test_workflow.name
        assert len(data["steps"]) == 1
        assert data["steps"][0]["step_key"] == "step1"
        assert "exported_at" in data

    @pytest.mark.asyncio
    async def test_import_workflow(self, client, test_user, test_organization, db_session):
        """Test importing workflow definition."""
        from app.core.security import create_token_pair
        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        export_data = {
            "workflow": {
                "name": "Imported Workflow",
                "description": "Imported from export",
                "tags": ["imported"],
                "metadata": {},
            },
            "version": {
                "version_number": 1,
                "definition": {},
                "steps": [],
                "connections": [],
                "variables": {},
            },
            "steps": [
                {
                    "step_key": "step1",
                    "name": "Step 1",
                    "step_type": "action",
                    "order": 0,
                    "handler": "mock_notification",
                    "config": {},
                    "input_mapping": {},
                    "output_mapping": {},
                    "timeout_seconds": 300,
                    "retry_policy_name": None,
                    "compensation_handler": None,
                    "compensation_config": {},
                    "depends_on": [],
                    "is_critical": True,
                    "continue_on_failure": False,
                }
            ],
            "retry_policies": [],
        }

        response = client.post(
            "/api/v1/workflows/import",
            json=export_data,
            headers=headers,
            params={"org_id": str(test_organization.id)},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Imported Workflow"
        assert data["status"] == "draft"


class TestRetryPolicies:
    """Tests for retry policy management."""

    @pytest.mark.asyncio
    async def test_create_retry_policy(self, client, test_user, test_organization):
        """Test creating a retry policy."""
        from app.core.security import create_token_pair
        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        response = client.post(
            "/api/v1/workflows/retry-policies",
            json={
                "name": "test-policy",
                "max_attempts": 5,
                "base_delay_seconds": 2.0,
                "max_delay_seconds": 120.0,
                "exponential_base": 2.0,
            },
            headers=headers,
            params={"org_id": str(test_organization.id)},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test-policy"
        assert data["max_attempts"] == 5

    @pytest.mark.asyncio
    async def test_create_retry_policy_duplicate(self, client, test_user, test_organization, db_session):
        """Test creating duplicate retry policy fails."""
        from app.core.security import create_token_pair
        from app.models.workflow import RetryPolicy
        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        policy = RetryPolicy(
            name="existing-policy",
            max_attempts=3,
            base_delay_seconds=1.0,
            max_delay_seconds=60.0,
            exponential_base=2.0,
        )
        db_session.add(policy)
        await db_session.commit()

        response = client.post(
            "/api/v1/workflows/retry-policies",
            json={
                "name": "existing-policy",
                "max_attempts": 5,
            },
            headers=headers,
            params={"org_id": str(test_organization.id)},
        )
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_list_retry_policies(self, client, test_user, test_organization, db_session):
        """Test listing retry policies."""
        from app.core.security import create_token_pair
        from app.models.workflow import RetryPolicy
        tokens = create_token_pair(test_user.id)
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        policy = RetryPolicy(
            name="policy1",
            max_attempts=3,
        )
        db_session.add(policy)
        await db_session.commit()

        response = client.get(
            "/api/v1/workflows/retry-policies",
            headers=headers,
            params={"org_id": str(test_organization.id)},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        names = [p["name"] for p in data]
        assert "policy1" in names