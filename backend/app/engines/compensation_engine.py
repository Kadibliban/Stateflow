"""
StateFlow Compensation Engine

Engine for executing compensation actions with retry support.
"""
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.execution import (
    CompensationExecution,
    StepExecution,
    StepStatus,
    WorkflowExecution,
)
from app.models.workflow import WorkflowStep
from app.repositories.execution_repository import CompensationExecutionRepository
from app.repositories.event_repository import ExecutionEventRepository
from app.models.event import ExecutionEvent, EventType
from app.workers.handlers import handler_registry

logger = get_logger(__name__)


class CompensationEngine:
    """Engine for executing compensation actions."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.comp_repo = CompensationExecutionRepository(session)
        self.event_repo = ExecutionEventRepository(session)

    async def execute_compensation(self, compensation_execution_id: UUID) -> Dict[str, Any]:
        """Execute a single compensation action."""
        comp_exec = await self.comp_repo.get_by_id(compensation_execution_id)
        if not comp_exec:
            raise ValueError("Compensation execution not found")

        # Get step execution first, then step definition
        step_exec = await self.session.get(StepExecution, comp_exec.step_execution_id)
        if not step_exec:
            raise ValueError("Step execution not found")

        step_def = await self.session.get(WorkflowStep, step_exec.step_def_id)
        if not step_def:
            raise ValueError("Step definition not found")

        workflow_execution = await self.session.get(WorkflowExecution, step_exec.execution_id)
        if not workflow_execution:
            raise ValueError("Workflow execution not found")

        # Get compensation handler
        handler = handler_registry.get_compensation(comp_exec.compensation_handler)
        if not handler:
            # Try to get from step definition
            handler = handler_registry.get_compensation(step_def.compensation_handler) if step_def else None

        if not handler:
            # No compensation handler - mark as completed (no-op)
            logger.info("No compensation handler, marking as completed", step_key=comp_exec.step_key)
            comp_exec.status = StepStatus.COMPENSATED
            comp_exec.completed_at = datetime.now(timezone.utc)
            comp_exec.output_data = {"status": "no_compensation_needed"}
            await self.session.commit()

            await self._log_event(
                execution_id=workflow_execution.id,
                event_type=EventType.COMPENSATION_COMPLETED,
                message=f"Compensation for {comp_exec.step_key} skipped (no handler)",
                compensation_execution_id=comp_exec.id,
            )
            return {"status": "completed", "output": {"status": "no_compensation_needed"}}

        # Update status to running
        comp_exec.status = StepStatus.COMPENSATING
        comp_exec.started_at = datetime.now(timezone.utc)
        comp_exec.worker_id = f"worker-{asyncio.current_task().get_name() if asyncio.current_task() else 'unknown'}"
        await self.session.commit()

        await self._log_event(
            execution_id=workflow_execution.id,
            event_type=EventType.COMPENSATION_STARTED,
            message=f"Compensation for {comp_exec.step_key} started",
            compensation_execution_id=comp_exec.id,
        )

        try:
            # Execute compensation handler with timeout
            start_time = datetime.now(timezone.utc)
            timeout = comp_exec.compensation_config.get("timeout_seconds", step_def.timeout_seconds)
            output_data = await asyncio.wait_for(
                handler(comp_exec.input_data, comp_exec.compensation_config),
                timeout=timeout,
            )
            end_time = datetime.now(timezone.utc)

            # Update compensation execution
            comp_exec.status = StepStatus.COMPENSATED
            comp_exec.output_data = output_data
            comp_exec.completed_at = end_time
            comp_exec.duration_ms = int((end_time - start_time).total_seconds() * 1000)

            await self.session.commit()

            await self._log_event(
                execution_id=workflow_execution.id,
                event_type=EventType.COMPENSATION_COMPLETED,
                message=f"Compensation for {comp_exec.step_key} completed",
                compensation_execution_id=comp_exec.id,
                event_data={"output_keys": list(output_data.keys())},
            )

            return {"status": "completed", "output": output_data}

        except asyncio.TimeoutError:
            # Handle compensation timeout
            timeout = comp_exec.compensation_config.get("timeout_seconds", step_def.timeout_seconds)
            error_msg = f"Compensation timed out after {timeout} seconds"
            return await self._handle_compensation_failure(
                workflow_execution, comp_exec, step_def, error_msg,
                {"exception_type": "TimeoutError", "timeout_seconds": timeout},
                retryable=True,  # Timeouts are generally retryable
            )

        except Exception as e:
            # Handle compensation failure with error classification
            from app.engines.retry_engine import RetryEngine
            retry_engine = RetryEngine(self.session)

            # Get retry policy for error classification
            retryable_errors = []
            non_retryable_errors = []
            if step_def.retry_policy:
                retryable_errors = step_def.retry_policy.retryable_errors or []
                non_retryable_errors = step_def.retry_policy.non_retryable_errors or []

            is_retryable = await retry_engine.classify_error(
                e, retryable_errors=retryable_errors, non_retryable_errors=non_retryable_errors
            )

            return await self._handle_compensation_failure(
                workflow_execution, comp_exec, step_def, str(e),
                {"exception_type": type(e).__name__},
                retryable=is_retryable,
            )

    async def _handle_compensation_failure(
        self,
        workflow_execution: WorkflowExecution,
        comp_exec: CompensationExecution,
        step_def: WorkflowStep,
        error_msg: str,
        error_details: Dict[str, Any],
        retryable: bool,
    ) -> Dict[str, Any]:
        """Handle compensation failure with retry logic based on error classification."""
        comp_exec.status = StepStatus.COMPENSATION_FAILED
        comp_exec.error = error_msg
        comp_exec.error_details = error_details
        comp_exec.completed_at = datetime.now(timezone.utc)
        await self.session.commit()

        await self._log_event(
            execution_id=workflow_execution.id,
            event_type=EventType.COMPENSATION_FAILED,
            message=f"Compensation for {comp_exec.step_key} failed: {error_msg}",
            compensation_execution_id=comp_exec.id,
            event_data={"error": error_msg, **error_details},
        )

        # Check if we should retry based on error classification
        if retryable and comp_exec.attempt < comp_exec.max_attempts:
            from app.engines.retry_engine import RetryEngine
            retry_engine = RetryEngine(self.session)
            await retry_engine.schedule_compensation_retry(comp_exec)
            return {"status": "retrying", "error": error_msg, "retry_scheduled": True}

        # If not retryable or max attempts reached
        if comp_exec.attempt >= comp_exec.max_attempts:
            await self._log_event(
                execution_id=workflow_execution.id,
                event_type=EventType.COMPENSATION_RETRY_EXHAUSTED,
                message=f"Compensation for {comp_exec.step_key} max retries exhausted",
                compensation_execution_id=comp_exec.id,
            )

        return {"status": "failed", "error": error_msg, "retryable": retryable}

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