"""
StateFlow Workflow Engine

Core engine for executing workflow steps in sequence with dependency resolution.
"""
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.execution import (
    WorkflowExecution,
    StepExecution,
    ExecutionStatus,
    StepStatus,
)
from app.models.idempotency import IdempotencyRecord
from app.models.workflow import Workflow, WorkflowVersion, WorkflowStep
from app.repositories.execution_repository import (
    ExecutionRepository,
    StepExecutionRepository,
    IdempotencyRepository,
)
from app.repositories.event_repository import ExecutionEventRepository
from app.models.event import ExecutionEvent, EventType
from app.workers.handlers import handler_registry

logger = get_logger(__name__)


class WorkflowEngine:
    """Engine for executing workflows."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.exec_repo = ExecutionRepository(session)
        self.step_repo = StepExecutionRepository(session)
        self.idempotency_repo = IdempotencyRepository(session)
        self.event_repo = ExecutionEventRepository(session)

    async def execute_workflow(self, execution_id: UUID) -> Dict[str, Any]:
        """Execute a complete workflow."""
        execution = await self.exec_repo.get_with_steps(execution_id)
        if not execution:
            raise ValueError("Execution not found")

        if execution.status != ExecutionStatus.PENDING:
            raise ValueError(f"Execution is not in pending state: {execution.status}")

        # Get workflow version with steps
        version = await self.session.get(WorkflowVersion, execution.version_id)
        if not version:
            raise ValueError("Workflow version not found")

        steps = await self.session.execute(
            select(WorkflowStep)
            .where(WorkflowStep.version_id == version.id)
            .order_by(WorkflowStep.order)
        )
        steps = steps.scalars().all()

        if not steps:
            raise ValueError("Workflow has no steps")

        # Create step executions
        step_executions = []
        for step in steps:
            step_exec = StepExecution(
                execution_id=execution_id,
                step_def_id=step.id,
                step_key=step.step_key,
                status=StepStatus.PENDING,
                input_data={},
                output_data={},
                error_details={},
                attempt=1,
                max_attempts=step.retry_policy.max_attempts if step.retry_policy else 3,
            )
            self.session.add(step_exec)
            step_executions.append(step_exec)

        await self.session.flush()

        # Update execution status
        execution.status = ExecutionStatus.RUNNING
        execution.started_at = datetime.now(timezone.utc)
        execution.current_step = step_executions[0].step_key if step_executions else None

        await self.session.commit()

        # Log event
        await self._log_event(
            execution_id=execution_id,
            event_type=EventType.EXECUTION_STARTED,
            message=f"Workflow execution started with {len(steps)} steps",
        )

        # Execute steps in order (respecting dependencies)
        completed_steps: Set[str] = set()
        failed_step: Optional[StepExecution] = None
        remaining_steps = list(step_executions)

        while remaining_steps and not failed_step:
            # Find next step with satisfied dependencies
            next_step_idx = None
            next_step_def = None
            for idx, step_exec in enumerate(remaining_steps):
                step_def = next(s for s in steps if s.id == step_exec.step_def_id)
                if await self._check_dependencies(step_def, completed_steps):
                    next_step_idx = idx
                    next_step_def = step_def
                    break

            if next_step_idx is None:
                # No executable steps - check if there are waiting steps (circular dependency or bug)
                waiting_steps = [s for s in remaining_steps if s.status == StepStatus.WAITING]
                if waiting_steps:
                    logger.error("Circular dependency or unsatisfiable dependencies detected")
                    failed_step = waiting_steps[0]
                    failed_step.error = "Circular dependency or unsatisfiable dependencies"
                    failed_step.error_details = {"type": "DependencyError"}
                    failed_step.status = StepStatus.FAILED
                    break
                # No more executable steps but some remain - shouldn't happen
                break

            # Execute the next executable step
            step_exec = remaining_steps.pop(next_step_idx)

            # Prepare input data
            step_exec.input_data = self._prepare_input(next_step_def, execution.context, completed_steps)

            # Execute step
            try:
                result = await self.execute_step(step_exec.id)
                if result.get("status") == "completed":
                    completed_steps.add(next_step_def.step_key)
                    execution.completed_steps = list(completed_steps)
                    execution.current_step = await self._get_next_step(next_step_def, steps, completed_steps)
                else:
                    failed_step = step_exec
                    break
            except Exception as e:
                logger.error("Step execution failed", step_key=next_step_def.step_key, error=str(e))
                failed_step = step_exec
                break

            await self.session.commit()

        # Handle completion or failure
        if failed_step:
            await self._handle_failure(execution, failed_step)
        else:
            await self._handle_completion(execution)

        return {"execution_id": str(execution_id), "status": execution.status.value}

    async def execute_step(self, step_execution_id: UUID) -> Dict[str, Any]:
        """Execute a single step with idempotency and error classification."""
        step_exec = await self.step_repo.get_by_id(step_execution_id)
        if not step_exec:
            raise ValueError("Step execution not found")

        step_def = await self.session.get(WorkflowStep, step_exec.step_def_id)
        if not step_def:
            raise ValueError("Step definition not found")

        execution = await self.exec_repo.get_by_id(step_exec.execution_id)
        if not execution:
            raise ValueError("Workflow execution not found")

        # Check step-level idempotency
        if step_exec.idempotency_key:
            existing = await self.idempotency_repo.get_valid_by_key("step", step_exec.idempotency_key)
            if existing and existing.completed:
                # Return cached result
                logger.info("Step execution skipped due to idempotency", step_key=step_def.step_key)
                return existing.response_data

        # Update status to running
        step_exec.status = StepStatus.RUNNING
        step_exec.started_at = datetime.now(timezone.utc)
        step_exec.worker_id = f"worker-{asyncio.current_task().get_name() if asyncio.current_task() else 'unknown'}"
        await self.session.commit()

        await self._log_event(
            execution_id=execution.id,
            event_type=EventType.STEP_STARTED,
            message=f"Step {step_def.step_key} started",
            step_execution_id=step_exec.id,
        )

        # Get handler
        handler = handler_registry.get_handler(step_def.handler)
        if not handler:
            raise ValueError(f"Handler not found: {step_def.handler}")

        try:
            # Execute handler with timeout
            start_time = datetime.now(timezone.utc)
            output_data = await asyncio.wait_for(
                handler(step_exec.input_data, step_def.config),
                timeout=step_def.timeout_seconds,
            )
            end_time = datetime.now(timezone.utc)

            # Update step execution
            step_exec.status = StepStatus.COMPLETED
            step_exec.output_data = output_data
            step_exec.completed_at = end_time
            step_exec.duration_ms = int((end_time - start_time).total_seconds() * 1000)

            # Update execution context with step output
            if execution.context is None:
                execution.context = {}
            execution.context[step_def.step_key] = output_data

            # Apply output mapping
            for target_key, source_expr in step_def.output_mapping.items():
                # Simple mapping: source_expr is a key in output_data
                if source_expr in output_data:
                    execution.context[target_key] = output_data[source_expr]

            await self.session.commit()

            # Mark idempotency record as completed
            if step_exec.idempotency_key:
                await self.idempotency_repo.complete(
                    existing.id if (existing := await self.idempotency_repo.get_valid_by_key("step", step_exec.idempotency_key)) else None,
                    {"status": "completed", "output": output_data},
                    200,
                )

            await self._log_event(
                execution_id=execution.id,
                event_type=EventType.STEP_COMPLETED,
                message=f"Step {step_def.step_key} completed",
                step_execution_id=step_exec.id,
                event_data={"output_keys": list(output_data.keys())},
            )

            return {"status": "completed", "output": output_data}

        except asyncio.TimeoutError:
            # Handle step timeout
            error_msg = f"Step timed out after {step_def.timeout_seconds} seconds"
            return await self._handle_step_failure(
                execution, step_exec, step_def, error_msg,
                {"exception_type": "TimeoutError", "timeout_seconds": step_def.timeout_seconds},
                retryable=True,  # Timeouts are generally retryable
            )

        except Exception as e:
            # Handle step failure with error classification
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

            return await self._handle_step_failure(
                execution, step_exec, step_def, str(e),
                {"exception_type": type(e).__name__},
                retryable=is_retryable,
            )

    async def _handle_step_failure(
        self,
        execution: WorkflowExecution,
        step_exec: StepExecution,
        step_def: WorkflowStep,
        error_msg: str,
        error_details: Dict[str, Any],
        retryable: bool,
    ) -> Dict[str, Any]:
        """Handle step failure with retry logic based on error classification."""
        step_exec.status = StepStatus.FAILED
        step_exec.error = error_msg
        step_exec.error_details = error_details
        step_exec.completed_at = datetime.now(timezone.utc)
        await self.session.commit()

        await self._log_event(
            execution_id=execution.id,
            event_type=EventType.STEP_FAILED,
            message=f"Step {step_def.step_key} failed: {error_msg}",
            step_execution_id=step_exec.id,
            event_data={"error": error_msg, **error_details},
        )

        # Check if we should retry based on error classification
        if retryable and step_exec.attempt < step_exec.max_attempts:
            from app.engines.retry_engine import RetryEngine
            retry_engine = RetryEngine(self.session)
            await retry_engine.schedule_retry(step_exec)
            return {"status": "retrying", "error": error_msg, "retry_scheduled": True}

        # If not retryable or max attempts reached
        if step_exec.attempt >= step_exec.max_attempts:
            await self._log_event(
                execution_id=execution.id,
                event_type=EventType.STEP_RETRY_EXHAUSTED,
                message=f"Step {step_def.step_key} max retries exhausted",
                step_execution_id=step_exec.id,
            )

        return {"status": "failed", "error": error_msg, "retryable": retryable}

    async def _check_dependencies(
        self, step_def: WorkflowStep, completed_steps: Set[str]
    ) -> bool:
        """Check if all dependencies are satisfied."""
        for dep in step_def.depends_on:
            if dep not in completed_steps:
                return False
        return True

    def _prepare_input(
        self,
        step_def: WorkflowStep,
        context: Dict[str, Any],
        completed_steps: Set[str],
    ) -> Dict[str, Any]:
        """Prepare input data for step from context and mappings."""
        input_data = {}

        # Apply input mapping
        for target_key, source_expr in step_def.input_mapping.items():
            # source_expr can be a context key or a static value
            if source_expr in context:
                input_data[target_key] = context[source_expr]
            else:
                # Try to parse as static value or expression
                input_data[target_key] = source_expr

        return input_data

    async def _get_next_step(
        self,
        current_step: WorkflowStep,
        all_steps: List[WorkflowStep],
        completed_steps: Set[str],
    ) -> Optional[str]:
        """Get the next step to execute."""
        for step in all_steps:
            if step.step_key not in completed_steps and step.step_key != current_step.step_key:
                if await self._check_dependencies(step, completed_steps):
                    return step.step_key
        return None

    async def _handle_failure(
        self,
        execution: WorkflowExecution,
        failed_step: StepExecution,
    ) -> None:
        """Handle workflow failure."""
        execution.status = ExecutionStatus.FAILED
        execution.failed_step = failed_step.step_key
        execution.error = failed_step.error
        execution.error_details = failed_step.error_details
        execution.completed_at = datetime.now(timezone.utc)

        await self.session.commit()

        await self._log_event(
            execution_id=execution.id,
            event_type=EventType.EXECUTION_FAILED,
            message=f"Workflow failed at step {failed_step.step_key}: {failed_step.error}",
        )

    async def _handle_completion(self, execution: WorkflowExecution) -> None:
        """Handle workflow completion."""
        execution.status = ExecutionStatus.COMPLETED
        execution.completed_at = datetime.now(timezone.utc)
        execution.output_data = execution.context or {}

        await self.session.commit()

        await self._log_event(
            execution_id=execution.id,
            event_type=EventType.EXECUTION_COMPLETED,
            message="Workflow completed successfully",
        )

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