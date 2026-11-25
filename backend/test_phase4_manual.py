#!/usr/bin/env python
"""
Manual test script for Phase 4 Workflow Execution API endpoints.
Run this against a running backend server.
"""
import asyncio
import json
from uuid import uuid4

import httpx


BASE_URL = "http://localhost:8000"
API_PREFIX = "/api/v1"


async def test_phase4():
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
            "description": "A test workflow for Phase 4",
            "tags": ["test", "phase4"],
        }
        response = await client.post(f"{API_PREFIX}/workflows", json=workflow_data, headers=org_headers, params=org_params)
        print(f"Create Workflow: {response.status_code}")
        if response.status_code != 201:
            print(f"  Error: {response.text}")
            return
        workflow = response.json()
        workflow_id = workflow["id"]
        print(f"  Workflow created: {workflow['name']} ({workflow_id})")

        # 5. Create steps with mock handlers that have compensation
        print("\n=== Testing Step Creation (with compensation) ===")
        # Get version
        response = await client.get(f"{API_PREFIX}/workflows/{workflow_id}/versions", headers=org_headers, params=org_params)
        versions = response.json()
        version_number = versions[0]["version_number"] if versions else 1
        print(f"  Using version: {version_number}")

        # Step 1: mock_payment with compensation
        step_data = {
            "step_key": "step1",
            "name": "Payment Step",
            "step_type": "action",
            "handler": "mock_payment",
            "config": {"amount": 100},
            "order": 0,
            "compensation_handler": "mock_payment",  # Built-in handler has compensation
        }
        response = await client.post(
            f"{API_PREFIX}/workflows/{workflow_id}/steps",
            json=step_data,
            headers=org_headers,
            params={"version_number": version_number, **org_params},
        )
        print(f"Create Step 1: {response.status_code}")
        if response.status_code != 201:
            print(f"  Error: {response.text}")
        else:
            step = response.json()
            print(f"  Step created: {step['step_key']}")

        # Step 2: mock_inventory with compensation
        step2_data = {
            "step_key": "step2",
            "name": "Inventory Step",
            "step_type": "action",
            "handler": "mock_inventory",
            "config": {"items": ["item1", "item2"]},
            "order": 1,
            "depends_on": ["step1"],
            "compensation_handler": "mock_inventory",
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

        # Step 3: mock_shipping with compensation
        step3_data = {
            "step_key": "step3",
            "name": "Shipping Step",
            "step_type": "action",
            "handler": "mock_shipping",
            "config": {},
            "order": 2,
            "depends_on": ["step2"],
            "compensation_handler": "mock_shipping",
        }
        response = await client.post(
            f"{API_PREFIX}/workflows/{workflow_id}/steps",
            json=step3_data,
            headers=org_headers,
            params={"version_number": version_number, **org_params},
        )
        print(f"Create Step 3: {response.status_code}")
        if response.status_code != 201:
            print(f"  Error: {response.text}")
        else:
            step = response.json()
            print(f"  Step created: {step['step_key']}")

        # 6. Validate workflow
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

        # 7. Activate workflow
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

        # 8. Create workflow execution
        print("\n=== Testing Workflow Execution Creation ===")
        exec_data = {
            "input_data": {"order_id": "ORD-12345", "customer_id": "CUST-001"},
            "idempotency_key": f"idempotent-{uuid4().hex[:8]}",
        }
        response = await client.post(
            f"{API_PREFIX}/executions",
            json=exec_data,
            headers=org_headers,
            params={**org_params, "workflow_id": str(workflow_id)},
        )
        print(f"Create Execution: {response.status_code}")
        if response.status_code != 201:
            print(f"  Error: {response.text}")
            return
        execution = response.json()
        execution_id = execution["id"]
        print(f"  Execution created: {execution_id}")
        print(f"  Status: {execution['status']}")

        # 9. List executions
        print("\n=== Testing Execution List ===")
        response = await client.get(
            f"{API_PREFIX}/executions",
            headers=org_headers,
            params={**org_params, "workflow_id": str(workflow_id)},
        )
        print(f"List Executions: {response.status_code}")
        if response.status_code == 200:
            executions = response.json()
            print(f"  Found {executions['total']} executions")

        # 10. Get execution detail
        print("\n=== Testing Execution Detail ===")
        response = await client.get(
            f"{API_PREFIX}/executions/{execution_id}/detail",
            headers=org_headers,
            params=org_params,
        )
        print(f"Get Execution Detail: {response.status_code}")
        if response.status_code == 200:
            detail = response.json()
            print(f"  Execution: {detail['execution']['id']}")
            print(f"  Status: {detail['execution']['status']}")
            print(f"  Steps: {len(detail.get('steps', []))}")
            for s in detail.get('steps', []):
                print(f"    - {s['step_key']}: {s['status']}")

        # 11. Wait for execution to complete (poll)
        print("\n=== Waiting for Execution to Complete ===")
        max_wait = 60  # seconds
        wait_interval = 2
        waited = 0
        while waited < max_wait:
            await asyncio.sleep(wait_interval)
            waited += wait_interval

            response = await client.get(
                f"{API_PREFIX}/executions/{execution_id}",
                headers=org_headers,
                params=org_params,
            )
            if response.status_code == 200:
                execution = response.json()
                print(f"  Status: {execution['status']} (waited {waited}s)")
                if execution['status'] in ['completed', 'failed', 'compensated', 'partially_compensated', 'cancelled', 'timed_out']:
                    break

        # 12. Get final execution detail
        print("\n=== Final Execution Detail ===")
        response = await client.get(
            f"{API_PREFIX}/executions/{execution_id}/detail",
            headers=org_headers,
            params=org_params,
        )
        print(f"Get Execution Detail: {response.status_code}")
        if response.status_code == 200:
            detail = response.json()
            print(f"  Execution: {detail['execution']['id']}")
            print(f"  Status: {detail['execution']['status']}")
            print(f"  Output: {detail['execution'].get('output_data', {})}")
            print(f"  Steps: {len(detail.get('steps', []))}")
            for s in detail.get('steps', []):
                print(f"    - {s['step_key']}: {s['status']} (output: {s.get('output_data', {})})")
            print(f"  Compensations: {len(detail.get('compensations', []))}")
            for c in detail.get('compensations', []):
                print(f"    - {c['step_key']}: {c['status']} (output: {c.get('output_data', {})})")

        # 13. Test idempotency - try to create same execution again
        print("\n=== Testing Idempotency ===")
        response = await client.post(
            f"{API_PREFIX}/executions",
            json=exec_data,
            headers=org_headers,
            params={**org_params, "workflow_id": str(workflow_id)},
        )
        print(f"Create Duplicate Execution: {response.status_code}")
        if response.status_code == 201:
            dup_execution = response.json()
            print(f"  Returned existing execution: {dup_execution['id']}")
            if dup_execution['id'] == execution_id:
                print("  ✓ Idempotency working correctly!")

        # 14. Test retry failed execution (if failed)
        print("\n=== Testing Execution Retry ===")
        response = await client.get(
            f"{API_PREFIX}/executions/{execution_id}",
            headers=org_headers,
            params=org_params,
        )
        if response.status_code == 200:
            execution = response.json()
            if execution['status'] in ['failed', 'compensated', 'partially_compensated']:
                response = await client.post(
                    f"{API_PREFIX}/executions/{execution_id}/retry",
                    headers=org_headers,
                    params=org_params,
                )
                print(f"Retry Execution: {response.status_code}")
                if response.status_code == 200:
                    retry_exec = response.json()
                    print(f"  Retried execution: {retry_exec['id']}")
                    print(f"  Status: {retry_exec['status']}")
            else:
                print(f"  Execution status is {execution['status']}, not retryable")

        print("\n=== All Phase 4 Tests Completed ===")


if __name__ == "__main__":
    asyncio.run(test_phase4())