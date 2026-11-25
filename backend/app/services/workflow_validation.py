"""
StateFlow Workflow Validation

Validation logic for workflow definitions, steps, and connections.
"""
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

from app.models.workflow import Workflow, WorkflowVersion, WorkflowStep, StepType
from app.core.logging import get_logger

logger = get_logger(__name__)


class WorkflowValidationError(Exception):
    """Exception raised for workflow validation errors."""

    def __init__(self, message: str, errors: List[str] = None):
        self.message = message
        self.errors = errors or []
        super().__init__(message)


class WorkflowValidator:
    """Validates workflow definitions and steps."""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate_workflow_definition(
        self,
        workflow: Workflow,
        version: WorkflowVersion,
        steps: List[WorkflowStep],
    ) -> Dict[str, Any]:
        """Validate a complete workflow definition."""
        self.errors = []
        self.warnings = []

        # Validate workflow
        self._validate_workflow(workflow)

        # Validate version
        self._validate_version(version)

        # Validate steps
        self._validate_steps(steps, version.id)

        # Validate connections/dependencies
        self._validate_dependencies(steps)

        # Check for cycles
        self._check_cycles(steps)

        # Validate step handlers
        self._validate_handlers(steps)

        return {
            "valid": len(self.errors) == 0,
            "errors": self.errors,
            "warnings": self.warnings,
        }

    def _validate_workflow(self, workflow: Workflow) -> None:
        """Validate workflow base properties."""
        if not workflow.name or not workflow.name.strip():
            self.errors.append("Workflow name is required")

        if workflow.status not in ["draft", "active", "deprecated", "archived"]:
            self.errors.append(f"Invalid workflow status: {workflow.status}")

        if workflow.current_version < 1:
            self.errors.append("Workflow current_version must be >= 1")

    def _validate_version(self, version: WorkflowVersion) -> None:
        """Validate workflow version."""
        if version.version_number < 1:
            self.errors.append("Version number must be >= 1")

        if not isinstance(version.definition, dict):
            self.errors.append("Version definition must be a dictionary")

        if not isinstance(version.steps, list):
            self.errors.append("Version steps must be a list")

        if not isinstance(version.connections, list):
            self.errors.append("Version connections must be a list")

        if not isinstance(version.variables, dict):
            self.errors.append("Version variables must be a dictionary")

    def _validate_steps(self, steps: List[WorkflowStep], version_id: UUID) -> None:
        """Validate workflow steps."""
        if not steps:
            self.errors.append("Workflow must have at least one step")
            return

        # Check for duplicate step keys
        step_keys = [s.step_key for s in steps]
        if len(step_keys) != len(set(step_keys)):
            duplicates = [k for k in step_keys if step_keys.count(k) > 1]
            self.errors.append(f"Duplicate step keys: {set(duplicates)}")

        # Check for duplicate orders
        orders = [s.order for s in steps]
        if len(orders) != len(set(orders)):
            duplicates = [o for o in orders if orders.count(o) > 1]
            self.errors.append(f"Duplicate step orders: {set(duplicates)}")

        # Validate each step
        for step in steps:
            self._validate_step(step, version_id)

        # Check step order continuity
        sorted_steps = sorted(steps, key=lambda s: s.order)
        expected_order = 0
        for step in sorted_steps:
            if step.order != expected_order:
                self.warnings.append(f"Step {step.step_key} has non-sequential order {step.order} (expected {expected_order})")
            expected_order += 1

    def _validate_step(self, step: WorkflowStep, version_id: UUID) -> None:
        """Validate a single step."""
        if not step.step_key or not step.step_key.strip():
            self.errors.append("Step key is required")

        if not step.name or not step.name.strip():
            self.errors.append(f"Step {step.step_key}: name is required")

        if not step.handler or not step.handler.strip():
            self.errors.append(f"Step {step.step_key}: handler is required")

        # Validate step type
        valid_types = [t.value for t in StepType]
        if step.step_type not in valid_types:
            self.errors.append(f"Step {step.step_key}: invalid step_type '{step.step_type}'. Valid types: {valid_types}")

        # Validate timeout
        if step.timeout_seconds < 1 or step.timeout_seconds > 3600:
            self.errors.append(f"Step {step.step_key}: timeout_seconds must be between 1 and 3600")

        # Validate retry policy
        if step.retry_policy_id:
            # This would need a DB check - skipped here
            pass

        # Validate depends_on references
        if step.depends_on:
            for dep in step.depends_on:
                if not isinstance(dep, str):
                    self.errors.append(f"Step {step.step_key}: dependency must be a string")
                # Note: We can't validate existence here without all steps loaded

        # Validate compensation for critical steps
        if step.is_critical and not step.compensation_handler and step.step_type != StepType.DELAY:
            self.warnings.append(f"Step {step.step_key} is critical but has no compensation handler")

    def _validate_dependencies(self, steps: List[WorkflowStep]) -> None:
        """Validate step dependencies."""
        step_keys = {s.step_key for s in steps}

        for step in steps:
            if step.depends_on:
                for dep in step.depends_on:
                    if dep not in step_keys:
                        self.errors.append(f"Step {step.step_key}: depends on non-existent step '{dep}'")

    def _check_cycles(self, steps: List[WorkflowStep]) -> None:
        """Check for circular dependencies."""
        # Build adjacency list
        graph: Dict[str, List[str]] = {}
        step_map = {s.step_key: s for s in steps}

        for step in steps:
            graph[step.step_key] = list(step.depends_on or [])

        # DFS cycle detection
        visited: Set[str] = set()
        rec_stack: Set[str] = set()

        def dfs(node: str, path: List[str]) -> bool:
            visited.add(node)
            rec_stack.add(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor, path + [neighbor]):
                        return True
                elif neighbor in rec_stack:
                    # Cycle detected
                    cycle_path = path + [neighbor]
                    cycle_start = cycle_path.index(neighbor)
                    cycle = cycle_path[cycle_start:]
                    self.errors.append(f"Circular dependency detected: {' -> '.join(cycle)}")
                    return True

            rec_stack.remove(node)
            return False

        for step_key in graph:
            if step_key not in visited:
                dfs(step_key, [step_key])

    def _validate_handlers(self, steps: List[WorkflowStep]) -> None:
        """Validate step handlers are registered."""
        from app.workers.handlers import handler_registry

        for step in steps:
            if not handler_registry.has_handler(step.handler):
                self.warnings.append(f"Step {step.step_key}: handler '{step.handler}' is not registered")

            if step.compensation_handler and not handler_registry.get_compensation(step.compensation_handler):
                # Check if the main handler has a built-in compensation
                main_handler_comp = handler_registry.get_compensation(step.handler)
                if not main_handler_comp:
                    self.warnings.append(f"Step {step.step_key}: compensation handler '{step.compensation_handler}' is not registered")


class WorkflowValidationService:
    """Service for validating workflows with database access."""

    def __init__(self, session):
        self.session = session
        self.validator = WorkflowValidator()

    async def validate_workflow_for_activation(
        self,
        workflow_id: UUID,
        version_number: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Validate a workflow before activation."""
        from app.repositories.workflow_repository import WorkflowRepository, WorkflowVersionRepository, WorkflowStepRepository

        workflow_repo = WorkflowRepository(self.session)
        version_repo = WorkflowVersionRepository(self.session)
        step_repo = WorkflowStepRepository(self.session)

        workflow = await workflow_repo.get_by_id(workflow_id)
        if not workflow:
            return {"valid": False, "errors": ["Workflow not found"], "warnings": []}

        version_num = version_number or workflow.current_version
        version = await version_repo.get_by_workflow_and_number(workflow_id, version_num)
        if not version:
            return {"valid": False, "errors": ["Workflow version not found"], "warnings": []}

        steps = await step_repo.list_steps(version.id)

        return self.validator.validate_workflow_definition(workflow, version, steps)

    async def validate_step_dependencies(
        self,
        version_id: UUID,
        new_step_key: str,
        new_depends_on: List[str],
        exclude_step_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Validate that step dependencies don't create cycles."""
        from app.repositories.workflow_repository import WorkflowStepRepository

        step_repo = WorkflowStepRepository(self.session)
        steps = await step_repo.list_steps(version_id)

        # Create a temporary list with the new step
        from app.models.workflow import WorkflowStep
        temp_step = WorkflowStep(
            version_id=version_id,
            step_key=new_step_key,
            name="temp",
            handler="temp",
            depends_on=new_depends_on,
        )
        all_steps = list(steps) + [temp_step]

        # Exclude the old step if updating
        if exclude_step_key:
            all_steps = [s for s in all_steps if s.step_key != exclude_step_key]

        validator = WorkflowValidator()
        validator._validate_dependencies(all_steps)
        validator._check_cycles(all_steps)

        return {
            "valid": len(validator.errors) == 0,
            "errors": validator.errors,
            "warnings": validator.warnings,
        }

    def validate_step_config(self, handler: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate step configuration for a specific handler."""
        from app.workers.handlers import handler_registry

        errors = []
        warnings = []

        # Handler-specific validation
        if handler == "http":
            if not config.get("url"):
                errors.append("HTTP handler requires 'url' in config")
            if config.get("method") not in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                warnings.append("HTTP method should be one of: GET, POST, PUT, DELETE, PATCH")

        elif handler == "function":
            if not config.get("function"):
                errors.append("Function handler requires 'function' in config")

        elif handler == "delay":
            seconds = config.get("seconds", 1)
            if not isinstance(seconds, (int, float)) or seconds < 0:
                errors.append("Delay handler 'seconds' must be a non-negative number")
            if seconds > 3600:
                warnings.append("Delay longer than 1 hour may cause timeouts")

        elif handler in ["mock_payment", "mock_inventory", "mock_shipping", "mock_notification"]:
            # These are built-in mock handlers - no special config needed
            pass

        else:
            # Custom handler - can't validate config
            warnings.append(f"Handler '{handler}' is custom - config validation skipped")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }