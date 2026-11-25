#!/usr/bin/env python
"""
Manual test script for Phase 4 compensation and retry testing.
Run this against a running backend server.
"""
import asyncio
import json
from uuid import uuid4

import httpx

BASE_URL = "http://localhost:8000"
API_PREFIX = "/api/v1"

# Add a failing handler to the registry
async def failing_handler(input_data: dict, config: dict) -> dict:
    """Mock handler that always fails."""
    await asyncio.sleep(0.1)
    raise Exception("Simulated failure for testing compensation")

async def failing_compensation(input_data: dict, config: dict) -> dict:
    """Mock compensation that succeeds."""
    await asyncio.sleep(0.1)
    return {"status": "compensated", "compensation_id": f"comp_{uuid4().hex[:12]}"}


async def test_compensation():
    # Register the failing handler dynamically
    from app.workers.handlers import handler_registry
    handler_registry.register("mock_failing", failing_handler, failing_compensation)

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

        org_headers = {**headers, "X-Organization-ID": str(org_id)}
        org_params = {"org_id": str(org_id)}

        # 4. Create workflow
        print("\n=== Testing Workflow Creation ===")
        workflow_data = {
            "name": "Failing Workflow",
            "description": "A test workflow that fails for compensation testing",
            "tags": ["test", "phase4", "compensation"],
        }
        response = await client.post(f"{API_PREFIX}/workflows", json=workflow_data, headers=org_headers, params=org_params)
        print(f"Create Workflow: {response.status_code}")
        if response.status_code != 201:
            print(f"  Error: {response.text}")
            return
        workflow = response.json()
        workflow_id = workflow["id"]
        print(f"  Workflow created: {workflow['name']} ({workflow_id})")

        # 5. Create steps - one that succeeds, one that fails
        print("\n=== Testing Step Creation (with failing step) ===")
        response = await client.get(f"{API_PREFIX}/workflows/{workflow_id}/versions", headers=org_headers, params=org_params)
        versions = response.json()
        version_number = versions[0]["version_number"] if versions else 1
        print(f"  Using version: {version_number}")

        # Step 1: mock_payment (succeeds)
        step_data = {
            "step_key": "step1",
            "name": "Payment Step",
            "step_type": "action",
            "handler": "mock_payment",
            "config": {"amount": 100},
            "order": 0,
            "compensation_handler": "mock_payment",
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

        # Step 2: mock_failing (will fail)
        step2_data = {
            "step_key": "step2",
            "name": "Failing Step",
            "step_type": "action",
            "handler": "mock_failing",
            "config": {"should_fail": True},
            "order": 1,
            "depends_on": ["step1"],
            "compensation_handler": "mock_failing",  # Has compensation
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

        # Step 3: mock_shipping (never reached due to failure)
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
            "input_data": {"order_id": "ORD-FAIL-123", "customer_id": "CUST-001"},
            "idempotency_key": f"idempotent-fail-{uuid4().hex[:8]}",
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

        # 9. Wait for execution to fail (poll)
        print("\n=== Waiting for Execution to Fail ===")
        max_wait = 120  # seconds - increased from 60
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
                if execution['status'] in ['failed', 'compensated', 'partially_compensated', 'cancelled', 'timed_out']:
                    break

        # 10. Get execution detail
        print("\n=== Execution Detail After Failure ===")
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
            print(f"  Error: {detail['execution'].get('error', 'N/A')}")
            print(f"  Steps: {len(detail.get('steps', []))}")
            for s in detail.get('steps', []):
                print(f"    - {s['step_key']}: {s['status']} (error: {s.get('error', 'N/A')})")
            print(f"  Compensations: {len(detail.get('compensations', []))}")
            for c in detail.get('compensations', []):
                print(f"    - {c['step_key']}: {c['status']} (output: {c.get('output_data', {})})")

        # 11. Test manual compensation trigger
        print("\n=== Testing Manual Compensation Trigger ===")
        response = await client.get(
            f"{API_PREFIX}/executions/{execution_id}",
            headers=org_headers,
            params=org_params,
        )
        if response.status_code == 200:
            execution = response.json()
            if execution['status'] in ['failed', 'partially_compensated']:
                response = await client.post(
                    f"{API_PREFIX}/executions/{execution_id}/compensate",
                    headers=org_headers,
                    params=org_params,
                )
                print(f"Trigger Compensation: {response.status_code}")
                if response.status_code == 200:
                    comp_exec = response.json()
                    print(f"  Compensation triggered, status: {comp_exec['status']}")

                    # Wait for compensation to complete
                    waited = 0
                    while waited < 30:
                        await asyncio.sleep(2)
                        waited += 2
                        response = await client.get(
                            f"{API_PREFIX}/executions/{execution_id}",
                            headers=org_headers,
                            params=org_params,
                        )
                        if response.status_code == 200:
                            execution = response.json()
                            print(f"  Status: {execution['status']} (waited {waited}s)")
                            if execution['status'] in ['compensated', 'partially_compensated']:
                                break

                    # Get final detail
                    response = await client.get(
                        f"{API_PREFIX}/executions/{execution_id}/detail",
                        headers=org_headers,
                        params=org_params,
                    )
                    if response.status_code == 200:
                        detail = response.json()
                        print(f"  Final status: {detail['execution']['status']}")
                        print(f"  Compensations: {len(detail.get('compensations', []))}")
                        for c in detail.get('compensations', []):
                            print(f"    - {c['step_key']}: {c['status']} (output: {c.get('output_data', {})})")
            else:
                print(f"  Execution status is {execution['status']}, not compensatable")

        # 12. Test retry
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

                    # Wait for retry to complete
                    waited = 0
                    while waited < 60:
                        await asyncio.sleep(2)
                        waited += 2
                        response = await client.get(
                            f"{API_PREFIX}/executions/{retry_exec['id']}",
                            headers=org_headers,
                            params=org_params,
                        )
                        if response.status_code == 200:
                            execution = response.json()
                            print(f"  Status: {execution['status']} (waited {waited}s)")
                            if execution['status'] in ['completed', 'failed', 'compensated', 'partially_compensated', 'cancelled', 'timed_out']:
                                break

                    # Get final detail
                    response = await client.get(
                        f"{API_PREFIX}/executions/{retry_exec['id']}/detail",
                        headers=org_headers,
                        params=org_params,
                    )
                    if response.status_code == 200:
                        detail = response.json()
                        print(f"  Final status: {detail['execution']['status']}")
                        print(f"  Steps: {len(detail.get('steps', []))}")
                        for s in detail.get('steps', []):
                            print(f"    - {s['step_key']}: {s['status']} (output: {s.get('output_data', {})})")
            else:
                print(f"  Execution status is {execution['status']}, not retryable")

        print("\n=== All Compensation Tests Completed ===")


if __name__ == "__main__":
    asyncio.run(test_compensation())