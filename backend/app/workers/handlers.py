"""
StateFlow Step Handler Registry

Registry for step execution handlers with support for custom handlers.
"""
import asyncio
import logging
from typing import Any, Callable, Dict, Optional, Awaitable
from uuid import UUID

from app.core.logging import get_logger

logger = get_logger(__name__)

# Type alias for handler functions
HandlerFunc = Callable[[Dict[str, Any], Dict[str, Any]], Awaitable[Dict[str, Any]]]
CompensationFunc = Callable[[Dict[str, Any], Dict[str, Any]], Awaitable[Dict[str, Any]]]


class StepHandlerRegistry:
    """Registry for step execution handlers."""

    def __init__(self):
        self._handlers: Dict[str, HandlerFunc] = {}
        self._compensation_handlers: Dict[str, CompensationFunc] = {}
        self._register_builtin_handlers()

    def _register_builtin_handlers(self) -> None:
        """Register built-in handlers for demo/testing."""

        # HTTP call handler
        async def http_handler(input_data: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
            """Execute an HTTP request."""
            import httpx

            url = config.get("url")
            method = config.get("method", "POST")
            headers = config.get("headers", {})
            timeout = config.get("timeout", 30)

            if not url:
                raise ValueError("URL is required for HTTP handler")

            async with httpx.AsyncClient(timeout=timeout) as client:
                if method == "GET":
                    response = await client.get(url, params=input_data, headers=headers)
                elif method == "POST":
                    response = await client.post(url, json=input_data, headers=headers)
                elif method == "PUT":
                    response = await client.put(url, json=input_data, headers=headers)
                elif method == "DELETE":
                    response = await client.delete(url, headers=headers)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                response.raise_for_status()
                return response.json() if response.content else {}

        # Compensation for HTTP
        async def http_compensation(input_data: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
            """Compensate an HTTP call (e.g., delete created resource)."""
            comp_config = config.get("compensation", {})
            url = comp_config.get("url")
            method = comp_config.get("method", "DELETE")

            if not url:
                raise ValueError("Compensation URL is required")

            import httpx
            async with httpx.AsyncClient(timeout=30) as client:
                if method == "DELETE":
                    response = await client.delete(url)
                elif method == "POST":
                    response = await client.post(url, json={})
                else:
                    raise ValueError(f"Unsupported compensation method: {method}")

                return {"status": response.status_code}

        self.register("http", http_handler, http_compensation)

        # Function call handler
        async def function_handler(input_data: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
            """Execute a Python function."""
            func_path = config.get("function")
            if not func_path:
                raise ValueError("Function path is required")

            # Import function dynamically
            module_path, func_name = func_path.rsplit(".", 1)
            module = __import__(module_path, fromlist=[func_name])
            func = getattr(module, func_name)

            if asyncio.iscoroutinefunction(func):
                return await func(input_data, config)
            else:
                return func(input_data, config)

        async def function_compensation(input_data: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
            """Compensate a function call."""
            comp_config = config.get("compensation", {})
            func_path = comp_config.get("function")
            if not func_path:
                raise ValueError("Compensation function path is required")

            module_path, func_name = func_path.rsplit(".", 1)
            module = __import__(module_path, fromlist=[func_name])
            func = getattr(module, func_name)

            if asyncio.iscoroutinefunction(func):
                return await func(input_data, comp_config)
            else:
                return func(input_data, comp_config)

        self.register("function", function_handler, function_compensation)

        # Mock/external service handlers for testing
        async def mock_payment_handler(input_data: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
            """Mock payment processing."""
            await asyncio.sleep(0.1)  # Simulate processing
            amount = input_data.get("amount", 0)
            return {
                "transaction_id": f"txn_{UUID(int=0).hex[:12]}",
                "amount": amount,
                "status": "completed",
            }

        async def mock_payment_compensation(input_data: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
            """Mock payment refund."""
            await asyncio.sleep(0.1)
            return {"refund_id": f"ref_{UUID(int=0).hex[:12]}", "status": "refunded"}

        self.register("mock_payment", mock_payment_handler, mock_payment_compensation)

        async def mock_inventory_handler(input_data: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
            """Mock inventory reservation."""
            await asyncio.sleep(0.1)
            items = input_data.get("items", [])
            return {
                "reservation_id": f"res_{UUID(int=0).hex[:12]}",
                "items": items,
                "status": "reserved",
            }

        async def mock_inventory_compensation(input_data: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
            """Mock inventory release."""
            await asyncio.sleep(0.1)
            return {"release_id": f"rel_{UUID(int=0).hex[:12]}", "status": "released"}

        self.register("mock_inventory", mock_inventory_handler, mock_inventory_compensation)

        async def mock_shipping_handler(input_data: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
            """Mock shipping creation."""
            await asyncio.sleep(0.1)
            return {
                "shipment_id": f"ship_{UUID(int=0).hex[:12]}",
                "tracking_number": f"TRK{UUID(int=0).hex[:12].upper()}",
                "status": "created",
            }

        async def mock_shipping_compensation(input_data: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
            """Mock shipping cancellation."""
            await asyncio.sleep(0.1)
            return {"cancellation_id": f"can_{UUID(int=0).hex[:12]}", "status": "cancelled"}

        self.register("mock_shipping", mock_shipping_handler, mock_shipping_compensation)

        async def mock_notification_handler(input_data: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
            """Mock notification sending."""
            await asyncio.sleep(0.05)
            return {
                "notification_id": f"notif_{UUID(int=0).hex[:12]}",
                "sent": True,
                "channels": input_data.get("channels", ["email"]),
            }

        async def mock_notification_compensation(input_data: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
            """Mock notification (no-op for notifications)."""
            return {"status": "no_compensation_needed"}

        self.register("mock_notification", mock_notification_handler, mock_notification_compensation)

        # Delay handler
        async def delay_handler(input_data: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
            """Wait for specified duration."""
            seconds = config.get("seconds", 1)
            await asyncio.sleep(seconds)
            return {"waited_seconds": seconds}

        self.register("delay", delay_handler, None)

        # Mock failing handler for testing compensation
        async def mock_failing_handler(input_data: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
            """Mock handler that always fails for testing."""
            await asyncio.sleep(0.1)
            raise Exception("Simulated failure for testing compensation")

        async def mock_failing_compensation(input_data: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
            """Mock compensation that succeeds."""
            await asyncio.sleep(0.1)
            return {"status": "compensated", "compensation_id": f"comp_{UUID(int=0).hex[:12]}"}

        self.register("mock_failing", mock_failing_handler, mock_failing_compensation)

        logger.info("Built-in handlers registered", handlers=list(self._handlers.keys()))

    def register(
        self,
        name: str,
        handler: HandlerFunc,
        compensation: Optional[CompensationFunc] = None,
    ) -> None:
        """Register a handler."""
        if name in self._handlers:
            logger.warning("Overwriting existing handler", handler=name)
        self._handlers[name] = handler
        if compensation:
            self._compensation_handlers[name] = compensation

    def unregister(self, name: str) -> bool:
        """Unregister a handler."""
        if name in self._handlers:
            del self._handlers[name]
            if name in self._compensation_handlers:
                del self._compensation_handlers[name]
            return True
        return False

    def get_handler(self, name: str) -> Optional[HandlerFunc]:
        """Get a handler by name."""
        return self._handlers.get(name)

    def get_compensation(self, name: str) -> Optional[CompensationFunc]:
        """Get a compensation handler by name."""
        return self._compensation_handlers.get(name)

    def has_handler(self, name: str) -> bool:
        """Check if handler exists."""
        return name in self._handlers

    def list_handlers(self) -> Dict[str, bool]:
        """List all handlers and whether they have compensation."""
        return {
            name: name in self._compensation_handlers
            for name in self._handlers
        }


# Global registry instance
handler_registry = StepHandlerRegistry()