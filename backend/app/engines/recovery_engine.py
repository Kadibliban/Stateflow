"""
StateFlow Recovery Engine

Engine for recovering in-flight executions after crashes or worker restarts.
"""
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.execution import (
    WorkflowExecution,
    StepExecution,
    CompensationExecution,
    ExecutionStatus,
    StepStatus,
)
from app.models.workflow import WorkflowStep
from app.repositories.execution_repository import (
    ExecutionRepository,
    StepExecutionRepository,
    CompensationExecutionRepository,
)
from app.repositories.event_repository import ExecutionEventRepository
from app.models.event import ExecutionEvent, EventType
# Lazy imports to avoid circular dependency
# from app.engines.workflow_engine import WorkflowEngine
# from app.engines.saga_engine import SagaEngine

logger = get_logger(__name__)


class RecoveryEngine:
    """Engine for recovering in-flight executions after crashes."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.exec_repo = ExecutionRepository(session)
        self.step_repo = StepExecutionRepository(session)
        self.comp_repo = CompensationExecutionRepository(session)
        self.event_repo = ExecutionEventRepository(session)

    async def recover_stale_executions(
        self,
        stale_threshold_minutes: int = 30,
        max_recoveries: int = 10,
    ) -> Dict[str, Any]:
        """
        Find and recover stale executions that were left in RUNNING state.

        This handles cases where a worker crashed mid-execution.
        """
        timeout = datetime.now(timezone.utc) - timedelta(minutes=stale_threshold_minutes)

        # Find executions stuck in RUNNING
        result = await self.session.execute(
            select(WorkflowExecution).where(
                WorkflowExecution.status == ExecutionStatus.RUNNING,
                WorkflowExecution.updated_at < timeout,
            ).limit(max_recoveries)
        )
        stale_executions = result.scalars().all()

        recovered = 0
        marked_timed_out = 0
        errors = []

        for execution in stale_executions:
            try:
                # Check if the execution was actually making progress recently
                # by looking at step executions
                steps = await self.step_repo.list_step_executions(execution.id)

                running_steps = [s for s in steps if s.status == StepStatus.RUNNING]
                completed_steps = [s for s in steps if s.status == StepStatus.COMPLETED]
                failed_steps = [s for s in steps if s.status == StepStatus.FAILED]
                retrying_steps = [s for s in steps if s.status == StepStatus.RETRYING]

                # If there are running steps but no recent progress, we need to recover
                if running_steps:
                    # Check if the running step has been running too long
                    for step in running_steps:
                        if step.started_at:
                            step_duration = datetime.now(timezone.utc) - step.started_at
                            if step_duration > timedelta(minutes=step_duration.total_seconds() / 60):
                                # Step timed out - mark as failed and let retry logic handle it
                                step.status = StepStatus.FAILED
                                step.error = f"Step timed out during recovery (was running for {step_duration})"
                                step.error_details = {"exception_type": "RecoveryTimeout"}
                                step.completed_at = datetime.now(timezone.utc)
                                await self.session.commit()

                # Determine recovery strategy based on state
                if failed_steps:
                    # Has failed steps - trigger compensation
                    execution.status = ExecutionStatus.FAILED
                    execution.failed_step = failed_steps[0].step_key
                    execution.error = failed_steps[0].error
                    execution.error_details = failed_steps[0].error_details
                    execution.completed_at = datetime.now(timezone.utc)
                    await self.session.commit()

                    # Log recovery event
                    await self._log_event(
                        execution_id=execution.id,
                        event_type=EventType.EXECUTION_FAILED,
                        message=f"Execution recovered and marked failed after worker crash: {execution.error}",
                    )

                    # Trigger compensation
                    # from app.engines.saga_engine import SagaEngine
                    # saga_engine = SagaEngine(self.session)
                    # Note: This would typically be triggered async via Celery
                    recovered += 1

                elif completed_steps and not running_steps:
                    # Was in progress but no running steps - continue from last completed
                    execution.status = ExecutionStatus.RUNNING
                    # Find next step to execute
                    await self._continue_execution(execution, steps)
                    recovered += 1

                else:
                    # Unclear state - mark as timed out for manual review
                    execution.status = ExecutionStatus.TIMED_OUT
                    execution.error = "Execution timed out during recovery - no clear state"
                    execution.completed_at = datetime.now(timezone.utc)
                    await self.session.commit()
                    marked_timed_out += 1

                    await self._log_event(
                        execution_id=execution.id,
                        event_type=EventType.EXECUTION_TIMED_OUT,
                        message="Execution marked timed out during recovery",
                    )

            except Exception as e:
                logger.error("Failed to recover execution", execution_id=str(execution.id), error=str(e))
                errors.append({"execution_id": str(execution.id), "error": str(e)})

        return {
            "recovered": recovered,
            "marked_timed_out": marked_timed_out,
            "errors": errors,
        }

    async def _continue_execution(
        self,
        execution: WorkflowExecution,
        completed_steps: List[StepExecution],
    ) -> None:
        """Continue execution from the last completed step."""
        completed_keys = {s.step_key for s in completed_steps}

        # Get workflow version with steps
        version = await self.session.get(WorkflowVersion, execution.version_id)
        if not version:
            return

        from sqlalchemy import select as sa_select
        steps_result = await self.session.execute(
            sa_select(WorkflowStep)
            .where(WorkflowStep.version_id == version.id)
            .order_by(WorkflowStep.order)
        )
        all_steps = steps_result.scalars().all()

        # Find next step that hasn't completed
        next_step_def = None
        for step_def in all_steps:
            if step_def.step_key not in completed_keys:
                # Check dependencies
                deps_satisfied = all(dep in completed_keys for dep in step_def.depends_on)
                if deps_satisfied:
                    next_step_def = step_def
                    break

        if next_step_def:
            execution.current_step = next_step_def.step_key
            execution.completed_steps = list(completed_keys)
            await self.session.commit()

            # Re-queue the workflow execution to continue
            # Import inside to avoid circular dependency
            from app.workers.execution_tasks import execute_workflow
            execute_workflow.delay(str(execution.id))
        else:
            # All steps done - mark as completed
            execution.status = ExecutionStatus.COMPLETED
            execution.completed_at = datetime.now(timezone.utc)
            execution.output_data = execution.context or {}
            await self.session.commit()

    async def recover_step_executions(
        self,
        max_recoveries: int = 50,
    ) -> Dict[str, Any]:
        """
        Recover individual step executions that were left in RUNNING state.

        This is called by the scheduler to handle individual step timeouts.
        """
        timeout = datetime.now(timezone.utc) - timedelta(minutes=10)

        # Find steps stuck in RUNNING
        result = await self.session.execute(
            select(StepExecution).where(
                StepExecution.status == StepStatus.RUNNING,
                StepExecution.started_at < timeout,
            ).limit(max_recoveries)
        )
        stale_steps = result.scalars().all()

        recovered = 0
        errors = []

        for step in stale_steps:
            try:
                step_def = await self.session.get(WorkflowStep, step.step_def_id)
                if not step_def:
                    continue

                # Check if step timed out
                if step.started_at:
                    step_duration = datetime.now(timezone.utc) - step.started_at
                    if step_duration > timedelta(seconds=step_def.timeout_seconds * 2):
                        # Mark as failed and schedule retry if applicable
                        step.status = StepStatus.FAILED
                        step.error = f"Step timed out during recovery (ran for {step_duration})"
                        step.error_details = {"exception_type": "RecoveryTimeout", "duration_seconds": step_duration.total_seconds()}
                        step.completed_at = datetime.now(timezone.utc)
                        await self.session.commit()

                        # Check if we should retry
                        if step.attempt < step.max_attempts:
                            from app.engines.retry_engine import RetryEngine
                            retry_engine = RetryEngine(self.session)
                            await retry_engine.schedule_retry(step)

                        execution = await self.session.get(WorkflowExecution, step.execution_id)
                        if execution:
                            await self._log_event(
                                execution_id=execution.id,
                                event_type=EventType.STEP_FAILED,
                                message=f"Step {step.step_key} timed out and recovered",
                                step_execution_id=step.id,
                                event_data={"error": step.error, "recovery": True},
                            )

                        recovered += 1

            except Exception as e:
                logger.error("Failed to recover step", step_id=str(step.id), error=str(e))
                errors.append({"step_id": str(step.id), "error": str(e)})

        return {"recovered": recovered, "errors": errors}

    async def recover_compensation_executions(
        self,
        max_recoveries: int = 50,
    ) -> Dict[str, Any]:
        """
        Recover compensation executions that were left in COMPENSATING state.
        """
        timeout = datetime.now(timezone.utc) - timedelta(minutes=10)

        # Find compensations stuck in COMPENSATING
        result = await self.session.execute(
            select(CompensationExecution).where(
                CompensationExecution.status == StepStatus.COMPENSATING,
                CompensationExecution.started_at < timeout,
            ).limit(max_recoveries)
        )
        stale_comps = result.scalars().all()

        recovered = 0
        errors = []

        for comp in stale_comps:
            try:
                step_exec = await self.session.get(StepExecution, comp.step_execution_id)
                if not step_exec:
                    continue

                step_def = await self.session.get(WorkflowStep, step_exec.step_def_id)
                if not step_def:
                    continue

                # Check if compensation timed out
                if comp.started_at:
                    comp_duration = datetime.now(timezone.utc) - comp.started_at
                    comp_timeout = comp.compensation_config.get("timeout_seconds", step_def.timeout_seconds)
                    if comp_duration > timedelta(seconds=comp_timeout * 2):
                        # Mark as failed and schedule retry if applicable
                        comp.status = StepStatus.COMPENSATION_FAILED
                        comp.error = f"Compensation timed out during recovery (ran for {comp_duration})"
                        comp.error_details = {"exception_type": "RecoveryTimeout", "duration_seconds": comp_duration.total_seconds()}
                        comp.completed_at = datetime.now(timezone.utc)
                        await self.session.commit()

                        # Check if we should retry
                        if comp.attempt < comp.max_attempts:
                            from app.engines.retry_engine import RetryEngine
                            retry_engine = RetryEngine(self.session)
                            await retry_engine.schedule_compensation_retry(comp)

                        execution = await self.session.get(WorkflowExecution, comp.execution_id)
                        if execution:
                            await self._log_event(
                                execution_id=execution.id,
                                event_type=EventType.COMPENSATION_FAILED,
                                message=f"Compensation for {comp.step_key} timed out and recovered",
                                compensation_execution_id=comp.id,
                                event_data={"error": comp.error, "recovery": True},
                            )

                        recovered += 1

            except Exception as e:
                logger.error("Failed to recover compensation", comp_id=str(comp.id), error=str(e))
                errors.append({"compensation_id": str(comp.id), "error": str(e)})

        return {"recovered": recovered, "errors": errors}

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