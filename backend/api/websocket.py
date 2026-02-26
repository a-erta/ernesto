"""
WebSocket manager with Redis pub/sub (production) and in-memory (local dev) fallback.

If REDIS_URL is set: events are published to Redis and fanned out to all
connected instances — safe for multi-process / multi-container deployments.

If REDIS_URL is empty: events are broadcast directly from the in-memory dict
on the current process — fine for single-process local development.
"""
import json
import asyncio
from typing import Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import structlog

from ..config import settings

log = structlog.get_logger()
ws_router = APIRouter()


# ---------------------------------------------------------------------------
# In-memory connection registry (used by both modes)
# ---------------------------------------------------------------------------

class _LocalRegistry:
    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, item_id: str, websocket: WebSocket):
        await websocket.accept()
        self._connections.setdefault(item_id, []).append(websocket)
        log.info("ws.connected", item_id=item_id)

    def disconnect(self, item_id: str, websocket: WebSocket):
        conns = self._connections.get(item_id, [])
        if websocket in conns:
            conns.remove(websocket)
        log.info("ws.disconnected", item_id=item_id)

    async def send_to_local(self, item_id: str, payload: str):
        dead = []
        for ws in self._connections.get(item_id, []):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(item_id, ws)


_registry = _LocalRegistry()


# ---------------------------------------------------------------------------
# Broadcast — Redis or in-memory
# ---------------------------------------------------------------------------

async def broadcast(item_id: str, data: Any):
    payload = json.dumps(data)
    if settings.use_redis:
        await _redis_publish(item_id, payload)
    else:
        await _registry.send_to_local(item_id, payload)


async def _redis_publish(item_id: str, payload: str):
    try:
        import redis.asyncio as aioredis  # type: ignore
        r = aioredis.from_url(settings.REDIS_URL)
        await r.publish(f"ernesto:item:{item_id}", payload)
        await r.aclose()
    except Exception as e:
        log.warning("ws.redis_publish_error", error=str(e))
        # Fallback to local delivery so the current process still works
        await _registry.send_to_local(item_id, payload)


# ---------------------------------------------------------------------------
# Redis subscriber (started once per process in production)
# ---------------------------------------------------------------------------

_redis_listener_tasks: dict[str, asyncio.Task] = {}


async def _start_redis_listener(item_id: str):
    if item_id in _redis_listener_tasks:
        return
    task = asyncio.create_task(_redis_listener_loop(item_id))
    _redis_listener_tasks[item_id] = task


async def _redis_listener_loop(item_id: str):
    try:
        import redis.asyncio as aioredis  # type: ignore
        r = aioredis.from_url(settings.REDIS_URL)
        pubsub = r.pubsub()
        await pubsub.subscribe(f"ernesto:item:{item_id}")
        async for message in pubsub.listen():
            if message["type"] == "message":
                await _registry.send_to_local(item_id, message["data"])
    except Exception as e:
        log.warning("ws.redis_listener_error", item_id=item_id, error=str(e))
    finally:
        _redis_listener_tasks.pop(item_id, None)


# ---------------------------------------------------------------------------
# Compatibility shim — keeps existing code working
# ---------------------------------------------------------------------------

class _ManagerShim:
    """Thin wrapper so existing `manager.broadcast(...)` calls keep working."""
    async def broadcast(self, item_id: str, data: Any):
        await broadcast(item_id, data)

    async def broadcast_all(self, data: Any):
        payload = json.dumps(data)
        for item_id in list(_registry._connections.keys()):
            await _registry.send_to_local(item_id, payload)


manager = _ManagerShim()


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@ws_router.websocket("/ws/{item_id}")
async def item_websocket(websocket: WebSocket, item_id: str):
    await _registry.connect(item_id, websocket)
    if settings.use_redis:
        await _start_redis_listener(item_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        _registry.disconnect(item_id, websocket)
