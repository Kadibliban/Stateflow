"""
StateFlow Execution Tasks

Celery tasks for workflow and step execution.
"""
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from celery import shared_task
from sqlalchemy import select, update

from app.core.database import get_session_context, close_db
from app.core.logging import get_logger
from app.models.execution import (
    WorkflowExecution,
    StepExecution,
    CompensationExecution,
    ExecutionStatus,
    StepStatus,
)
from app.models.workflow import Workflow, WorkflowVersion, WorkflowStep
from app.workers.handlers import StepHandlerRegistry

logger = get_logger(__name__)


def _run_async(coro):
    """Run an async coroutine in a new event loop, ensuring proper cleanup."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        # Close the database connections before closing the loop
        try:
            loop.run_until_complete(close_db())
        except Exception:
            pass
        loop.close()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def execute_workflow(self, execution_id: str) -> Dict[str, Any]:
    """Execute a workflow asynchronously."""
    from app.engines.workflow_engine import WorkflowEngine

    async def _execute():
        async with get_session_context() as session:
            engine = WorkflowEngine(session)
            return await engine.execute_workflow(UUID(execution_id))

    try:
        result = _run_async(_execute())
        return {"status": "success", "result": result}
    except Exception as exc:
        logger.error("Workflow execution failed", execution_id=execution_id, error=str(exc))
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def execute_step(self, step_execution_id: str) -> Dict[str, Any]:
    """Execute a single workflow step."""
    from app.engines.workflow_engine import WorkflowEngine

    async def _execute():
        async with get_session_context() as session:
            engine = WorkflowEngine(session)
            return await engine.execute_step(UUID(step_execution_id))

    try:
        result = _run_async(_execute())
        return {"status": "success", "result": result}
    except Exception as exc:
        logger.error("Step execution failed", step_execution_id=step_execution_id, error=str(exc))
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def execute_compensation(self, compensation_execution_id: str) -> Dict[str, Any]:
    """Execute a compensation action."""
    from app.engines.compensation_engine import CompensationEngine

    async def _execute():
        async with get_session_context() as session:
            engine = CompensationEngine(session)
            return await engine.execute_compensation(UUID(compensation_execution_id))

    try:
        result = _run_async(_execute())
        return {"status": "success", "result": result}
    except Exception as exc:
        logger.error("Compensation execution failed", compensation_execution_id=compensation_execution_id, error=str(exc))
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def execute_saga_compensation(self, execution_id: str) -> Dict[str, Any]:
    """Execute saga compensation for a failed workflow."""
    from app.engines.saga_engine import SagaEngine

    async def _execute():
        async with get_session_context() as session:
            engine = SagaEngine(session)
            return await engine.compensate_saga(UUID(execution_id))

    try:
        result = _run_async(_execute())
        return {"status": "success", "result": result}
    except Exception as exc:
        logger.error("Saga compensation failed", execution_id=execution_id, error=str(exc))
        raise self.retry(exc=exc)


@shared_task
def schedule_step_retry(step_execution_id: str, delay_seconds: float) -> Dict[str, Any]:
    """Schedule a step retry after delay."""
    import time
    time.sleep(delay_seconds)

    # Re-queue the step execution
    execute_step.delay(step_execution_id)
    return {"status": "scheduled", "step_execution_id": step_execution_id}


@shared_task
def schedule_compensation_retry(compensation_execution_id: str, delay_seconds: float) -> Dict[str, Any]:
    """Schedule a compensation retry after delay."""
    import time
    time.sleep(delay_seconds)

    execute_compensation.delay(compensation_execution_id)
    return {"status": "scheduled", "compensation_execution_id": compensation_execution_id}


# Health check task
@shared_task
def worker_health_check() -> Dict[str, Any]:
    """Worker health check task."""
    from app.core.database import check_db_connection

    async def _check():
        return await check_db_connection()

    healthy = _run_async(_check())
    return {
        "status": "healthy" if healthy else "unhealthy",
        "database": "connected" if healthy else "disconnected",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }