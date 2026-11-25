"""
StateFlow Event Publisher

RabbitMQ publisher for outbox events.
"""
import asyncio
import json
from typing import Any, Dict, Optional
from uuid import UUID

import aio_pika
from aio_pika import ExchangeType, Message, DeliveryMode

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class RabbitMQPublisher:
    """Async RabbitMQ publisher for outbox events."""

    def __init__(self):
        self._connection: Optional[aio_pika.Connection] = None
        self._channel: Optional[aio_pika.Channel] = None
        self._exchanges: Dict[str, aio_pika.Exchange] = {}

    async def connect(self) -> None:
        """Establish connection to RabbitMQ."""
        if self._connection and not self._connection.is_closed:
            return

        self._connection = await aio_pika.connect_robust(
            settings.RABBITMQ_URL,
            client_properties={"connection_name": "stateflow-publisher"},
        )
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=10)
        logger.info("RabbitMQ publisher connected")

    async def disconnect(self) -> None:
        """Close connection to RabbitMQ."""
        if self._channel and not self._channel.is_closed:
            await self._channel.close()
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
        self._exchanges.clear()
        logger.info("RabbitMQ publisher disconnected")

    async def _get_exchange(self, exchange_name: str) -> aio_pika.Exchange:
        """Get or create exchange."""
        if exchange_name not in self._exchanges:
            if not self._channel:
                await self.connect()
            exchange = await self._channel.declare_exchange(
                exchange_name,
                ExchangeType.TOPIC,
                durable=True,
            )
            self._exchanges[exchange_name] = exchange
        return self._exchanges[exchange_name]

    async def publish(
        self,
        exchange_name: str,
        routing_key: str,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
        message_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        """Publish a message to RabbitMQ."""
        if not self._channel or self._channel.is_closed:
            await self.connect()

        exchange = await self._get_exchange(exchange_name)

        message_body = json.dumps(payload, default=str).encode()

        message = Message(
            body=message_body,
            content_type="application/json",
            delivery_mode=DeliveryMode.PERSISTENT,
            headers=headers or {},
            message_id=message_id,
            correlation_id=correlation_id,
            timestamp=asyncio.get_event_loop().time(),
        )

        await exchange.publish(message, routing_key=routing_key)
        logger.debug(
            "Published message to RabbitMQ",
            exchange=exchange_name,
            routing_key=routing_key,
            message_id=message_id,
        )

    async def publish_batch(
        self,
        messages: list[Dict[str, Any]],
    ) -> int:
        """Publish multiple messages."""
        published = 0
        for msg in messages:
            try:
                await self.publish(
                    exchange_name=msg.get("exchange", "stateflow.events"),
                    routing_key=msg.get("routing_key", "event"),
                    payload=msg["payload"],
                    headers=msg.get("headers"),
                    message_id=msg.get("message_id"),
                    correlation_id=msg.get("correlation_id"),
                )
                published += 1
            except Exception as e:
                logger.error(
                    "Failed to publish message in batch",
                    error=str(e),
                    message=msg,
                )
                raise
        return published


# Global publisher instance
_publisher: Optional[RabbitMQPublisher] = None


async def get_publisher() -> RabbitMQPublisher:
    """Get or create the global publisher instance."""
    global _publisher
    if _publisher is None:
        _publisher = RabbitMQPublisher()
        await _publisher.connect()
    return _publisher


async def close_publisher() -> None:
    """Close the global publisher."""
    global _publisher
    if _publisher:
        await _publisher.disconnect()
        _publisher = None