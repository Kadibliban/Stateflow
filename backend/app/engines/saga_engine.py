"""
StateFlow Saga Engine

Saga pattern orchestrator for distributed transactions with compensation.
"""
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.workers.handlers import handler_registry

logger = get_logger(__name__)


class SagaEngine:
    """Saga pattern orchestrator for workflow execution with compensation."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.exec_repo = ExecutionRepository(session)
        self.step_repo = StepExecutionRepository(session)
        self.comp_repo = CompensationExecutionRepository(session)
        self.event_repo = ExecutionEventRepository(session)

    async def execute_saga(self, execution_id: UUID) -> Dict[str, Any]:
        """Execute a saga (workflow with compensation support)."""
        execution = await self.exec_repo.get_with_all(execution_id)
        if not execution:
            raise ValueError("Execution not found")

        # This is the main saga orchestration logic
        # For now, delegate to workflow engine for forward execution
        from app.engines.workflow_engine import WorkflowEngine
        workflow_engine = WorkflowEngine(self.session)
        return await workflow_engine.execute_workflow(execution_id)

    async def compensate_saga(self, execution_id: UUID) -> Dict[str, Any]:
        """Execute compensation for a failed saga."""
        execution = await self.exec_repo.get_with_all(execution_id)
        if not execution:
            raise ValueError("Execution not found")

        # Allow compensation for failed, partially compensated, or already compensating executions
        if execution.status not in [ExecutionStatus.FAILED, ExecutionStatus.PARTIALLY_COMPENSATED, ExecutionStatus.COMPENSATING]:
            raise ValueError("Can only compensate failed, partially compensated, or compensating executions")

        # Update status to compensating
        execution.status = ExecutionStatus.COMPENSATING
        execution.compensation_retry_count = 0
        await self.session.commit()

        await self._log_event(
            execution_id=execution_id,
            event_type=EventType.COMPENSATION_STARTED,
            message="Saga compensation started",
        )

        # Get completed steps in reverse order
        completed_steps = [
            s for s in execution.step_executions
            if s.status == StepStatus.COMPLETED
        ]
        completed_steps.sort(key=lambda s: s.started_at or datetime.min, reverse=True)

        compensation_results = []
        failed_compensations = []

        for step_exec in completed_steps:
            # Check if compensation already done
            existing_comp = await self.comp_repo.get_by_step_execution(step_exec.id)
            if existing_comp and existing_comp.status == StepStatus.COMPENSATED:
                continue

            # Create compensation execution
            step_def = await self.session.get(WorkflowStep, step_exec.step_def_id)
            if not step_def or not step_def.compensation_handler:
                # No compensation handler - skip
                logger.warning("No compensation handler for step", step_key=step_def.step_key if step_def else "unknown")
                continue

            comp_exec = await self.comp_repo.create(
                CompensationExecution(
                    execution_id=execution_id,
                    step_execution_id=step_exec.id,
                    step_key=step_exec.step_key,
                    compensation_handler=step_def.compensation_handler,
                    compensation_config=step_def.compensation_config,
                    status=StepStatus.PENDING,
                    input_data=step_exec.output_data,  # Use step output as compensation input
                    output_data={},
                    error_details={},
                    attempt=1,
                    max_attempts=step_def.retry_policy.max_attempts if step_def.retry_policy else 3,
                    original_failure=execution.error,
                )
            )

            # Execute compensation
            from app.engines.compensation_engine import CompensationEngine
            comp_engine = CompensationEngine(self.session)
            result = await comp_engine.execute_compensation(comp_exec.id)
            compensation_results.append(result)

            if result.get("status") != "completed":
                failed_compensations.append({
                    "step_key": step_exec.step_key,
                    "error": result.get("error"),
                })

            await self.session.commit()

        # Determine final status
        if failed_compensations:
            if len(failed_compensations) == len(compensation_results):
                execution.status = ExecutionStatus.PARTIALLY_COMPENSATED
            else:
                execution.status = ExecutionStatus.PARTIALLY_COMPENSATED
        else:
            execution.status = ExecutionStatus.COMPENSATED

        execution.completed_at = datetime.now(timezone.utc)
        await self.session.commit()

        await self._log_event(
            execution_id=execution_id,
            event_type=EventType.COMPENSATION_COMPLETED if not failed_compensations else EventType.COMPENSATION_FAILED,
            message=f"Compensation {'completed' if not failed_compensations else 'partially failed'}",
            event_data={"failed_count": len(failed_compensations)},
        )

        return {
            "execution_id": str(execution_id),
            "status": execution.status.value,
            "compensations": compensation_results,
            "failed": failed_compensations,
        }

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