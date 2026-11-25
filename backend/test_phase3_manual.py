#!/usr/bin/env python
"""
Manual test script for Phase 3 Workflow Management API endpoints.
Run this against a running backend server.
"""
import asyncio
import json
from uuid import uuid4

import httpx


BASE_URL = "http://localhost:8000"
API_PREFIX = "/api/v1"


async def test_phase3():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        # 1. Register a user
        print("\n=== Testing User Registration ===")
        register_data = {
            "email": f"test_{uuid4().hex[:8]}@example.com",
            "username": f"testuser_{uuid4().hex[:8]}",
            "password": "password123",
            "full_name": "Test User",
        }
        response = await client.post(f"{API_PREFIX}/auth/register", json=register_data)
        print(f"Register: {response.status_code}")
        if response.status_code != 201:
            print(f"  Error: {response.text}")
            return
        user_data = response.json()
        print(f"  User created: {user_data['username']}")

        # 2. Login
        print("\n=== Testing Login ===")
        login_data = {"username": register_data["username"], "password": "password123"}
        response = await client.post(f"{API_PREFIX}/auth/login", json=login_data)
        print(f"Login: {response.status_code}")
        if response.status_code != 200:
            print(f"  Error: {response.text}")
            return
        tokens = response.json()
        access_token = tokens["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}
        print(f"  Token obtained")

        # 3. Create organization
        print("\n=== Testing Organization Creation ===")
        org_data = {
            "name": f"Test Org {uuid4().hex[:8]}",
            "slug": f"test-org-{uuid4().hex[:8]}",
            "description": "Test organization",
        }
        response = await client.post(f"{API_PREFIX}/organizations", json=org_data, headers=headers)
        print(f"Create Org: {response.status_code}")
        if response.status_code != 201:
            print(f"  Error: {response.text}")
            return
        org_data = response.json()
        org_id = org_data["id"]
        print(f"  Organization created: {org_data['name']} ({org_id})")

        # Add org header (for endpoints that use it)
        org_headers = {**headers, "X-Organization-ID": str(org_id)}
        # Also pass org_id as query param
        org_params = {"org_id": str(org_id)}

        # 4. Create workflow
        print("\n=== Testing Workflow Creation ===")
        workflow_data = {
            "name": "Test Workflow",
            "description": "A test workflow for Phase 3",
            "tags": ["test", "phase3"],
        }
        response = await client.post(f"{API_PREFIX}/workflows", json=workflow_data, headers=org_headers, params=org_params)
        print(f"Create Workflow: {response.status_code}")
        if response.status_code != 201:
            print(f"  Error: {response.text}")
            return
        workflow = response.json()
        workflow_id = workflow["id"]
        print(f"  Workflow created: {workflow['name']} ({workflow_id})")

        # 5. List workflows
        print("\n=== Testing Workflow List ===")
        response = await client.get(f"{API_PREFIX}/workflows", headers=org_headers, params=org_params)
        print(f"List Workflows: {response.status_code}")
        workflows = response.json()
        print(f"  Found {len(workflows)} workflows")

        # 6. Get workflow
        print("\n=== Testing Get Workflow ===")
        response = await client.get(f"{API_PREFIX}/workflows/{workflow_id}", headers=org_headers, params=org_params)
        print(f"Get Workflow: {response.status_code}")
        wf = response.json()
        print(f"  Workflow: {wf['name']}, status: {wf['status']}")

        # 7. Update workflow
        print("\n=== Testing Workflow Update ===")
        response = await client.patch(
            f"{API_PREFIX}/workflows/{workflow_id}",
            json={"name": "Updated Workflow", "description": "Updated description"},
            headers=org_headers,
            params=org_params,
        )
        print(f"Update Workflow: {response.status_code}")
        if response.status_code == 200:
            wf = response.json()
            print(f"  Updated name: {wf['name']}")

        # 8. Add step to workflow (need version)
        print("\n=== Testing Step Creation ===")
        # First, get the current version to add steps to
        response = await client.get(f"{API_PREFIX}/workflows/{workflow_id}/versions", headers=org_headers, params=org_params)
        versions = response.json()
        version_number = versions[0]["version_number"] if versions else 1
        print(f"  Using version: {version_number}")

        step_data = {
            "step_key": "step1",
            "name": "First Step",
            "step_type": "action",
            "handler": "mock_notification",
            "config": {"channel": "email"},
            "order": 0,
        }
        response = await client.post(
            f"{API_PREFIX}/workflows/{workflow_id}/steps",
            json=step_data,
            headers=org_headers,
            params={"version_number": version_number, **org_params},
        )
        print(f"Create Step: {response.status_code}")
        if response.status_code != 201:
            print(f"  Error: {response.text}")
        else:
            step = response.json()
            print(f"  Step created: {step['step_key']}")

        # Add second step with dependency
        step2_data = {
            "step_key": "step2",
            "name": "Second Step",
            "step_type": "action",
            "handler": "mock_payment",
            "config": {"amount": 100},
            "order": 1,
            "depends_on": ["step1"],
        }
        response = await client.post(
            f"{API_PREFIX}/workflows/{workflow_id}/steps",
            json=step2_data,
            headers=org_headers,
            params={"version_number": version_number, **org_params},
        )
        print(f"Create Step 2: {response.status_code}")
        if response.status_code != 201:
            print(f"  Error: {response.text}")
        else:
            step = response.json()
            print(f"  Step created: {step['step_key']}")

        # 9. List steps
        print("\n=== Testing Step List ===")
        response = await client.get(
            f"{API_PREFIX}/workflows/{workflow_id}/steps",
            headers=org_headers,
            params={"version_number": version_number, **org_params},
        )
        print(f"List Steps: {response.status_code}")
        steps = response.json()
        print(f"  Found {len(steps)} steps")
        for s in steps:
            print(f"    - {s['step_key']}: {s['name']} (depends_on: {s.get('depends_on', [])})")

        # 10. Update step
        print("\n=== Testing Step Update ===")
        response = await client.patch(
            f"{API_PREFIX}/workflows/{workflow_id}/steps/step1",
            json={"name": "Updated Step 1", "config": {"channel": "sms"}},
            headers=org_headers,
            params={"version_number": version_number, **org_params},
        )
        print(f"Update Step: {response.status_code}")
        if response.status_code == 200:
            step = response.json()
            print(f"  Updated name: {step['name']}, config: {step['config']}")

        # 11. Validate workflow
        print("\n=== Testing Workflow Validation ===")
        response = await client.post(
            f"{API_PREFIX}/workflows/{workflow_id}/validate",
            headers=org_headers,
            params=org_params,
        )
        print(f"Validate Workflow: {response.status_code}")
        if response.status_code == 200:
            validation = response.json()
            print(f"  Valid: {validation['valid']}")
            print(f"  Errors: {validation.get('errors', [])}")
            print(f"  Warnings: {validation.get('warnings', [])}")

        # 12. Test validation with no steps (should fail)
        print("\n=== Testing Validation (No Steps) ===")
        # Create a new workflow without steps
        wf_data = {"name": "Empty Workflow", "description": "No steps"}
        response = await client.post(f"{API_PREFIX}/workflows", json=wf_data, headers=org_headers, params=org_params)
        if response.status_code == 201:
            empty_wf = response.json()
            response = await client.post(
                f"{API_PREFIX}/workflows/{empty_wf['id']}/validate",
                headers=org_headers,
                params=org_params,
            )
            print(f"Validate Empty Workflow: {response.status_code}")
            if response.status_code == 200:
                validation = response.json()
                print(f"  Valid: {validation['valid']}")
                print(f"  Errors: {validation.get('errors', [])}")

        # 13. Activate workflow
        print("\n=== Testing Workflow Activation ===")
        response = await client.post(
            f"{API_PREFIX}/workflows/{workflow_id}/activate",
            headers=org_headers,
            params=org_params,
        )
        print(f"Activate Workflow: {response.status_code}")
        if response.status_code == 200:
            wf = response.json()
            print(f"  Status: {wf['status']}, version: {wf['current_version']}")

        # 14. Get workflow definition (visual editor)
        print("\n=== Testing Workflow Definition ===")
        response = await client.get(
            f"{API_PREFIX}/workflows/{workflow_id}/definition",
            headers=org_headers,
            params=org_params,
        )
        print(f"Get Definition: {response.status_code}")
        if response.status_code == 200:
            definition = response.json()
            print(f"  Workflow: {definition['workflow']['name']}")
            print(f"  Steps: {len(definition.get('steps', []))}")

        # 15. Clone workflow
        print("\n=== Testing Workflow Clone ===")
        response = await client.post(
            f"{API_PREFIX}/workflows/{workflow_id}/clone",
            headers=org_headers,
            params={"name": "Cloned Workflow", **org_params},
        )
        print(f"Clone Workflow: {response.status_code}")
        if response.status_code == 201:
            cloned = response.json()
            print(f"  Cloned: {cloned['name']} ({cloned['id']})")
            cloned_id = cloned["id"]

            # Verify steps were cloned
            response = await client.get(
                f"{API_PREFIX}/workflows/{cloned_id}/steps",
                headers=org_headers,
                params=org_params,
            )
            if response.status_code == 200:
                steps = response.json()
                print(f"  Cloned steps: {len(steps)}")

        # 16. Export workflow
        print("\n=== Testing Workflow Export ===")
        response = await client.get(
            f"{API_PREFIX}/workflows/{workflow_id}/export",
            headers=org_headers,
            params=org_params,
        )
        print(f"Export Workflow: {response.status_code}")
        if response.status_code == 200:
            export = response.json()
            print(f"  Exported workflow: {export['workflow']['name']}")
            print(f"  Steps: {len(export.get('steps', []))}")
            print(f"  Retry policies: {len(export.get('retry_policies', []))}")

            # 17. Import workflow
            print("\n=== Testing Workflow Import ===")
            # Modify the name to avoid duplicate
            export["workflow"]["name"] = "Imported Workflow"
            response = await client.post(
                f"{API_PREFIX}/workflows/import",
                json=export,
                headers=org_headers,
                params=org_params,
            )
            print(f"Import Workflow: {response.status_code}")
            if response.status_code == 201:
                imported = response.json()
                print(f"  Imported: {imported['name']} ({imported['id']})")

        # 18. Test retry policies
        print("\n=== Testing Retry Policies ===")
        rp_data = {
            "name": f"test-retry-policy-{uuid4().hex[:8]}",
            "max_attempts": 5,
            "base_delay_seconds": 2.0,
            "max_delay_seconds": 120.0,
            "exponential_base": 2.0,
        }
        response = await client.post(
            f"{API_PREFIX}/workflows/retry-policies",
            json=rp_data,
            headers=org_headers,
            params=org_params,
        )
        print(f"Create Retry Policy: {response.status_code}")
        if response.status_code == 201:
            rp = response.json()
            print(f"  Created: {rp['name']}")

        response = await client.get(
            f"{API_PREFIX}/workflows/retry-policies",
            headers=org_headers,
            params=org_params,
        )
        print(f"List Retry Policies: {response.status_code}")
        if response.status_code == 200:
            rps = response.json()
            print(f"  Found {len(rps)} policies")

        # 19. Test step with retry policy
        print("\n=== Testing Step with Retry Policy ===")
        response = await client.get(
            f"{API_PREFIX}/workflows/retry-policies",
            headers=org_headers,
            params=org_params,
        )
        if response.status_code == 200:
            rps = response.json()
            if rps:
                rp_id = rps[0]["id"]
                step_data = {
                    "step_key": "step3",
                    "name": "Step with Retry",
                    "step_type": "action",
                    "handler": "mock_notification",
                    "config": {},
                    "order": 2,
                    "retry_policy_id": rp_id,
                }
                response = await client.post(
                    f"{API_PREFIX}/workflows/{workflow_id}/steps",
                    json=step_data,
                    headers=org_headers,
                    params={"version_number": version_number, **org_params},
                )
                print(f"Create Step with Retry Policy: {response.status_code}")
                if response.status_code != 201:
                    print(f"  Error: {response.text}")

        # 20. Test delete step
        print("\n=== Testing Step Deletion ===")
        response = await client.delete(
            f"{API_PREFIX}/workflows/{workflow_id}/steps/step3",
            headers=org_headers,
            params={"version_number": version_number, **org_params},
        )
        print(f"Delete Step: {response.status_code}")

        # 21. Test delete step with dependency (should fail)
        print("\n=== Testing Delete Step with Dependency (should fail) ===")
        response = await client.delete(
            f"{API_PREFIX}/workflows/{workflow_id}/steps/step1",
            headers=org_headers,
            params={"version_number": version_number, **org_params},
        )
        print(f"Delete Step with Dependency: {response.status_code}")
        if response.status_code == 400:
            print(f"  Correctly rejected: {response.json().get('detail', 'No detail')}")

        # 22. Deactivate workflow
        print("\n=== Testing Workflow Deactivation ===")
        response = await client.post(
            f"{API_PREFIX}/workflows/{workflow_id}/deactivate",
            headers=org_headers,
            params=org_params,
        )
        print(f"Deactivate Workflow: {response.status_code}")
        if response.status_code == 200:
            wf = response.json()
            print(f"  Status: {wf['status']}")

        # 23. Test update workflow when active (should fail)
        print("\n=== Testing Update Active Workflow (should fail) ===")
        # Reactivate first
        await client.post(f"{API_PREFIX}/workflows/{workflow_id}/activate", headers=org_headers, params=org_params)
        response = await client.patch(
            f"{API_PREFIX}/workflows/{workflow_id}",
            json={"name": "Should Fail"},
            headers=org_headers,
            params=org_params,
        )
        print(f"Update Active Workflow: {response.status_code}")
        if response.status_code == 400:
            print(f"  Correctly rejected")

        # Deactivate again
        await client.post(f"{API_PREFIX}/workflows/{workflow_id}/deactivate", headers=org_headers, params=org_params)

        # 24. Test delete workflow (should work when deactivated)
        print("\n=== Testing Workflow Deletion ===")
        response = await client.delete(
            f"{API_PREFIX}/workflows/{workflow_id}",
            headers=org_headers,
            params=org_params,
        )
        print(f"Delete Workflow: {response.status_code}")

        print("\n=== All Phase 3 Tests Completed ===")


if __name__ == "__main__":
    asyncio.run(test_phase3())