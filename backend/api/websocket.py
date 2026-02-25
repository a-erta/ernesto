"""
WebSocket manager — broadcasts real-time agent state updates to connected UI clients.
"""
import json
from typing import Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import structlog

log = structlog.get_logger()

ws_router = APIRouter()


class ConnectionManager:
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

    async def broadcast(self, item_id: str, data: Any):
        payload = json.dumps(data)
        dead = []
        for ws in self._connections.get(item_id, []):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(item_id, ws)

    async def broadcast_all(self, data: Any):
        payload = json.dumps(data)
        for item_id, conns in self._connections.items():
            dead = []
            for ws in conns:
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self.disconnect(item_id, ws)


manager = ConnectionManager()


@ws_router.websocket("/ws/{item_id}")
async def item_websocket(websocket: WebSocket, item_id: str):
    await manager.connect(item_id, websocket)
    try:
        while True:
            # Keep connection alive; client sends pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(item_id, websocket)
