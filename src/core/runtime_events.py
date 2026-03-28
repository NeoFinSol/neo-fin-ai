from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - optional runtime dependency
    Redis = None

from src.core.ws_manager import ws_manager
from src.models.settings import app_settings

logger = logging.getLogger(__name__)

_EVENT_CHANNEL = "neofin:ws-events"


def _events_redis_url() -> str | None:
    return app_settings.task_events_redis_url or app_settings.task_queue_broker_url


def _use_redis_event_bridge() -> bool:
    return (
        Redis is not None
        and app_settings.task_runtime == "celery"
        and bool(_events_redis_url())
    )


async def broadcast_task_event(task_id: str, message: dict[str, Any]) -> None:
    """Send runtime event either directly or through Redis pub/sub."""
    if not _use_redis_event_bridge():
        await ws_manager.broadcast(task_id, message)
        return

    redis_url = _events_redis_url()
    if not redis_url:
        await ws_manager.broadcast(task_id, message)
        return

    try:
        client = Redis.from_url(redis_url, decode_responses=True)
        await client.publish(
            _EVENT_CHANNEL,
            json.dumps({"task_id": task_id, "message": message}, ensure_ascii=False),
        )
        await client.aclose()
    except Exception as exc:
        logger.warning("Failed to publish runtime event for %s: %s", task_id, exc)


async def _event_listener_loop(redis_url: str) -> None:
    client = Redis.from_url(redis_url, decode_responses=True)
    pubsub = client.pubsub()
    await pubsub.subscribe(_EVENT_CHANNEL)
    logger.info("Runtime event bridge subscribed to %s", _EVENT_CHANNEL)

    try:
        while True:
            payload = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=1.0,
            )
            if payload is None:
                await asyncio.sleep(0.05)
                continue

            try:
                message = json.loads(payload["data"])
                task_id = message["task_id"]
                body = message["message"]
                if isinstance(task_id, str) and isinstance(body, dict):
                    await ws_manager.broadcast(task_id, body)
            except Exception as exc:
                logger.warning("Failed to handle runtime event payload: %s", exc)
    except asyncio.CancelledError:
        logger.info("Runtime event bridge stopped")
        raise
    finally:
        await pubsub.unsubscribe(_EVENT_CHANNEL)
        await pubsub.aclose()
        await client.aclose()


@asynccontextmanager
async def runtime_event_bridge() -> AsyncIterator[None]:
    """Run Redis-to-WebSocket bridge only for persistent runtime."""
    if not _use_redis_event_bridge():
        yield
        return

    redis_url = _events_redis_url()
    if not redis_url:
        logger.warning("Persistent runtime enabled without TASK_EVENTS_REDIS_URL")
        yield
        return

    listener = asyncio.create_task(
        _event_listener_loop(redis_url),
        name="runtime-event-bridge",
    )
    try:
        yield
    finally:
        listener.cancel()
        try:
            await listener
        except asyncio.CancelledError:
            pass
