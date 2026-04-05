from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    """Manage active websocket connections (single-instance placeholder)."""

    def __init__(self) -> None:
        self._rooms: dict[str, list[WebSocket]] = defaultdict(list)

    def connect(self, room_id: str, websocket: WebSocket) -> None:
        self._rooms[room_id].append(websocket)

    def disconnect(self, room_id: str, websocket: WebSocket) -> None:
        room_connections = self._rooms.get(room_id, [])
        if websocket in room_connections:
            room_connections.remove(websocket)
        if not room_connections and room_id in self._rooms:
            del self._rooms[room_id]

    async def broadcast(
        self,
        room_id: str,
        message: dict[str, Any],
        exclude: WebSocket | None = None,
    ) -> None:
        room_connections = list(self._rooms.get(room_id, []))
        stale: list[WebSocket] = []

        for connection in room_connections:
            if exclude is not None and connection is exclude:
                continue
            try:
                await connection.send_json(message)
            except Exception:
                stale.append(connection)

        for connection in stale:
            self.disconnect(room_id, connection)