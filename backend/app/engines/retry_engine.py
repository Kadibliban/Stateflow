"""
StateFlow Retry Engine

Engine for managing retries with exponential backoff.
"""
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.execution import (
    StepExecution,
    CompensationExecution,
    StepStatus,
)
from app.models.workflow import WorkflowStep
from app.repositories.execution_repository import (
    StepExecutionRepository,
    CompensationExecutionRepository,
)
from app.repositories.event_repository import ExecutionEventRepository
from app.models.event import ExecutionEvent, EventType

logger = get_logger(__name__)


class RetryEngine:
    """Engine for managing retries with exponential backoff."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.step_repo = StepExecutionRepository(session)
        self.comp_repo = CompensationExecutionRepository(session)
        self.event_repo = ExecutionEventRepository(session)

    async def schedule_retry(self, step_execution: StepExecution) -> Dict[str, Any]:
        """Schedule a retry for a step execution."""
        step_def = await self.session.get(WorkflowStep, step_execution.step_def_id)
        if not step_def:
            raise ValueError("Step definition not found")

        # Get retry policy
        policy = step_def.retry_policy
        if policy:
            base_delay = policy.base_delay_seconds
            max_delay = policy.max_delay_seconds
            exponential_base = policy.exponential_base
            max_attempts = policy.max_attempts
        else:
            base_delay = settings.SAGA_RETRY_BASE_DELAY
            max_delay = settings.SAGA_RETRY_MAX_DELAY
            exponential_base = settings.SAGA_RETRY_EXPONENTIAL_BASE
            max_attempts = settings.SAGA_MAX_RETRIES

        # Check if we've exceeded max attempts
        if step_execution.attempt >= max_attempts:
            # Mark as retry exhausted
            step_execution.status = StepStatus.FAILED
            step_execution.error = f"Max retry attempts ({max_attempts}) exhausted"
            step_execution.completed_at = datetime.now(timezone.utc)
            await self.session.commit()

            execution = await self.session.get(type(step_execution), step_execution.execution_id)
            if execution:
                await self._log_event(
                    execution_id=execution.id,
                    event_type=EventType.STEP_RETRY_EXHAUSTED,
                    message=f"Step {step_execution.step_key} max retries exhausted",
                    step_execution_id=step_execution.id,
                )

            return {"status": "exhausted", "max_attempts": max_attempts}

        # Calculate delay with exponential backoff
        delay = min(
            base_delay * (exponential_base ** (step_execution.attempt - 1)),
            max_delay,
        )

        # Add jitter (±10%)
        import random
        jitter = delay * 0.1 * (random.random() * 2 - 1)
        delay = max(0.1, delay + jitter)

        next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)

        # Update step execution
        step_execution.status = StepStatus.RETRYING
        step_execution.next_retry_at = next_retry_at
        step_execution.attempt += 1
        await self.session.commit()

        execution = await self.session.get(type(step_execution), step_execution.execution_id)
        if execution:
            await self._log_event(
                execution_id=execution.id,
                event_type=EventType.RETRY_SCHEDULED,
                message=f"Retry scheduled for step {step_execution.step_key} (attempt {step_execution.attempt}/{max_attempts})",
                step_execution_id=step_execution.id,
                event_data={"delay_seconds": delay, "next_retry_at": next_retry_at.isoformat()},
            )

        # Schedule the retry task
        from app.workers.execution_tasks import schedule_step_retry
        schedule_step_retry.delay(str(step_execution.id), delay)

        return {
            "status": "scheduled",
            "attempt": step_execution.attempt,
            "max_attempts": max_attempts,
            "delay_seconds": delay,
            "next_retry_at": next_retry_at.isoformat(),
        }

    async def schedule_compensation_retry(self, comp_execution: CompensationExecution) -> Dict[str, Any]:
        """Schedule a retry for a compensation execution."""
        # Get retry policy from original step
        step_exec = await self.session.get(StepExecution, comp_execution.step_execution_id)
        if not step_exec:
            raise ValueError("Step execution not found")

        step_def = await self.session.get(WorkflowStep, step_exec.step_def_id)
        if not step_def:
            raise ValueError("Step definition not found")

        policy = step_def.retry_policy
        if policy:
            base_delay = policy.base_delay_seconds
            max_delay = policy.max_delay_seconds
            exponential_base = policy.exponential_base
            max_attempts = policy.max_attempts
        else:
            base_delay = settings.SAGA_RETRY_BASE_DELAY
            max_delay = settings.SAGA_RETRY_MAX_DELAY
            exponential_base = settings.SAGA_RETRY_EXPONENTIAL_BASE
            max_attempts = settings.SAGA_MAX_RETRIES

        if comp_execution.attempt >= max_attempts:
            comp_execution.status = StepStatus.COMPENSATION_FAILED
            comp_execution.error = f"Max compensation retry attempts ({max_attempts}) exhausted"
            comp_execution.completed_at = datetime.now(timezone.utc)
            await self.session.commit()

            execution = await self.session.get(type(step_exec), step_exec.execution_id)
            if execution:
                await self._log_event(
                    execution_id=execution.id,
                    event_type=EventType.COMPENSATION_RETRY_EXHAUSTED,
                    message=f"Compensation for {comp_execution.step_key} max retries exhausted",
                    compensation_execution_id=comp_execution.id,
                )

            return {"status": "exhausted", "max_attempts": max_attempts}

        # Calculate delay
        delay = min(
            base_delay * (exponential_base ** (comp_execution.attempt - 1)),
            max_delay,
        )

        import random
        jitter = delay * 0.1 * (random.random() * 2 - 1)
        delay = max(0.1, delay + jitter)

        next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)

        # Update compensation execution
        comp_execution.status = StepStatus.RETRYING
        comp_execution.next_retry_at = next_retry_at
        comp_execution.attempt += 1
        await self.session.commit()

        execution = await self.session.get(type(step_exec), step_exec.execution_id)
        if execution:
            await self._log_event(
                execution_id=execution.id,
                event_type=EventType.COMPENSATION_RETRYING,
                message=f"Compensation retry scheduled for {comp_execution.step_key} (attempt {comp_execution.attempt}/{max_attempts})",
                compensation_execution_id=comp_execution.id,
                event_data={"delay_seconds": delay, "next_retry_at": next_retry_at.isoformat()},
            )

        # Schedule the retry task
        from app.workers.execution_tasks import schedule_compensation_retry
        schedule_compensation_retry.delay(str(comp_execution.id), delay)

        return {
            "status": "scheduled",
            "attempt": comp_execution.attempt,
            "max_attempts": max_attempts,
            "delay_seconds": delay,
            "next_retry_at": next_retry_at.isoformat(),
        }

    async def classify_error(self, error: Exception, retryable_errors: list = None, non_retryable_errors: list = None) -> bool:
        """Classify if an error is retryable."""
        error_type = type(error).__name__
        error_message = str(error)

        # Check non-retryable first
        if non_retryable_errors:
            for non_retryable in non_retryable_errors:
                if non_retryable.lower() in error_type.lower() or non_retryable.lower() in error_message.lower():
                    return False

        # Check retryable
        if retryable_errors:
            for retryable in retryable_errors:
                if retryable.lower() in error_type.lower() or retryable.lower() in error_message.lower():
                    return True

        # Default: retry on common transient errors
        transient_errors = [
            "timeout",
            "connection",
            "network",
            "temporary",
            "unavailable",
            "rate limit",
            "throttl",
        ]
        for transient in transient_errors:
            if transient in error_type.lower() or transient in error_message.lower():
                return True

        # Non-retryable by default
        return False

    async def _log_event(
        self,
        execution_id: UUID,
        event_type: EventType,
        message: str,
        step_execution_id: Optional[UUID] = None,
        compensation_execution_id: Optional[UUID] = None,
        event_data: Optional[Dict[str, Any]] = None,
    ) -> ExecutionEvent:
        """Log an execution event."""
        event = ExecutionEvent(
            execution_id=execution_id,
            step_execution_id=step_execution_id,
            compensation_execution_id=compensation_execution_id,
            event_type=event_type,
            event_data=event_data or {},
            message=message,
            severity="info",
        )
        return await self.event_repo.create(event)