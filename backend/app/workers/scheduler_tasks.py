"""
StateFlow Scheduler Tasks

Celery tasks for scheduled operations like retries and cleanup.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import UUID

from celery import shared_task

from app.core.config import settings
from app.core.database import get_session_context
from app.core.logging import get_logger
from app.models.execution import (
    WorkflowExecution,
    StepExecution,
    CompensationExecution,
    ExecutionStatus,
    StepStatus,
)
from app.models.idempotency import IdempotencyRecord
from app.repositories.execution_repository import (
    ExecutionRepository,
    StepExecutionRepository,
    CompensationExecutionRepository,
    IdempotencyRepository,
)
from app.repositories.event_repository import OutboxRepository
from app.engines.recovery_engine import RecoveryEngine

logger = get_logger(__name__)


@shared_task
def retry_scheduler() -> Dict[str, Any]:
    """Check for steps and compensations ready for retry."""
    async def _schedule():
        async with get_session_context() as session:
            step_repo = StepExecutionRepository(session)
            comp_repo = CompensationExecutionRepository(session)

            # Get retryable steps
            retryable_steps = await step_repo.get_retryable_steps(limit=50)
            for step in retryable_steps:
                # Calculate exponential backoff delay
                from app.models.workflow import RetryPolicy
                from sqlalchemy import select

                delay = settings.SAGA_RETRY_BASE_DELAY
                if step.step_def and step.step_def.retry_policy:
                    policy = step.step_def.retry_policy
                    delay = min(
                        policy.base_delay_seconds * (policy.exponential_base ** (step.attempt - 1)),
                        policy.max_delay_seconds,
                    )

                # Schedule retry
                from app.workers.execution_tasks import schedule_step_retry
                schedule_step_retry.delay(str(step.id), delay)

            # Get retryable compensations
            retryable_comps = await comp_repo.get_retryable_compensations(limit=50)
            for comp in retryable_comps:
                delay = settings.SAGA_RETRY_BASE_DELAY
                if comp.step_execution and comp.step_execution.step_def and comp.step_execution.step_def.retry_policy:
                    policy = comp.step_execution.step_def.retry_policy
                    delay = min(
                        policy.base_delay_seconds * (policy.exponential_base ** (comp.attempt - 1)),
                        policy.max_delay_seconds,
                    )

                from app.workers.execution_tasks import schedule_compensation_retry
                schedule_compensation_retry.delay(str(comp.id), delay)

            return {
                "scheduled_steps": len(retryable_steps),
                "scheduled_compensations": len(retryable_comps),
            }

    try:
        result = asyncio.run(_schedule())
        return {"status": "success", "result": result}
    except Exception as exc:
        logger.error("Retry scheduler failed", error=str(exc))
        return {"status": "error", "error": str(exc)}


@shared_task
def cleanup_expired() -> Dict[str, Any]:
    """Clean up expired records."""
    async def _cleanup():
        async with get_session_context() as session:
            idempotency_repo = IdempotencyRepository(session)
            outbox_repo = OutboxRepository(session)

            # Clean up expired idempotency records
            idempotency_deleted = await idempotency_repo.cleanup_expired()

            # Clean up old published outbox events
            outbox_deleted = await outbox_repo.cleanup_old_published(days=30)

            # Clean up expired refresh tokens (handled by auth service)
            # Could add a token cleanup task here

            return {
                "idempotency_deleted": idempotency_deleted,
                "outbox_deleted": outbox_deleted,
            }

    try:
        result = asyncio.run(_cleanup())
        return {"status": "success", "result": result}
    except Exception as exc:
        logger.error("Cleanup failed", error=str(exc))
        return {"status": "error", "error": str(exc)}


@shared_task
def check_stale_executions() -> Dict[str, Any]:
    """Check for stale executions and recover them."""
    async def _check():
        async with get_session_context() as session:
            recovery_engine = RecoveryEngine(session)
            return await recovery_engine.recover_stale_executions(
                stale_threshold_minutes=30,
                max_recoveries=10,
            )

    try:
        result = asyncio.run(_check())
        return {"status": "success", "result": result}
    except Exception as exc:
        logger.error("Stale execution recovery failed", error=str(exc))
        return {"status": "error", "error": str(exc)}


@shared_task
def recover_step_executions() -> Dict[str, Any]:
    """Recover step executions stuck in RUNNING state."""
    async def _recover():
        async with get_session_context() as session:
            recovery_engine = RecoveryEngine(session)
            return await recovery_engine.recover_step_executions(max_recoveries=50)

    try:
        result = asyncio.run(_recover())
        return {"status": "success", "result": result}
    except Exception as exc:
        logger.error("Step execution recovery failed", error=str(exc))
        return {"status": "error", "error": str(exc)}


@shared_task
def recover_compensation_executions() -> Dict[str, Any]:
    """Recover compensation executions stuck in COMPENSATING state."""
    async def _recover():
        async with get_session_context() as session:
            recovery_engine = RecoveryEngine(session)
            return await recovery_engine.recover_compensation_executions(max_recoveries=50)

    try:
        result = asyncio.run(_recover())
        return {"status": "success", "result": result}
    except Exception as exc:
        logger.error("Compensation execution recovery failed", error=str(exc))
        return {"status": "error", "error": str(exc)}


import asyncio