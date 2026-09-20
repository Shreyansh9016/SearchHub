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

    async def broadcast(self, message: dict) -> None:
        for websocket in list(self.connections):
            try:
                await websocket.send_json(message)
            except Exception:
                self.remove(websocket)


manager = ConnectionManager()


def trending_message(db: Session) -> dict:
    return {
        "type": "trending",
        "queries": [{"query": q, "count": n} for q, n in trending_queries(db)],
    }
