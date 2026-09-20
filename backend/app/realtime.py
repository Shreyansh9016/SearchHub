from datetime import datetime, timezone

from fastapi import WebSocket
from sqlalchemy.orm import Session

from app.queries import trending_queries

PING_SECONDS = 25
IDLE_TIMEOUT = 60


class ConnectionManager:
    def __init__(self):
        self.connections: dict[WebSocket, int] = {}

    def add(self, websocket: WebSocket, user_id: int) -> None:
        self.connections[websocket] = user_id

    def remove(self, websocket: WebSocket) -> None:
        self.connections.pop(websocket, None)

    async def _send(self, websocket: WebSocket, message: dict) -> None:
        try:
            await websocket.send_json(message)
        except Exception:
            self.remove(websocket)

    async def broadcast(self, message: dict) -> None:
        for websocket in list(self.connections):
            await self._send(websocket, message)

    async def send_to_users(self, user_ids, message: dict) -> None:
        wanted = set(user_ids)
        for websocket, user_id in list(self.connections.items()):
            if user_id in wanted:
                await self._send(websocket, message)


manager = ConnectionManager()


def trending_message(db: Session) -> dict:
    return {
        "type": "trending",
        "queries": [{"query": q, "count": n} for q, n in trending_queries(db)],
    }


def activity_message(title: str, document_id: int) -> dict:
    return {
        "type": "activity",
        "message": f"Someone bookmarked {title}",
        "document_id": document_id,
        "at": datetime.now(timezone.utc).isoformat(),
    }


def notification_message(title: str, document_id: int) -> dict:
    return {
        "type": "notification",
        "message": f'"{title}" was updated',
        "document_id": document_id,
    }
