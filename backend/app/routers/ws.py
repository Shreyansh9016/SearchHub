import asyncio
import time

import jwt
from fastapi import APIRouter, Depends, Query, WebSocket
from sqlalchemy.orm import Session

from app import realtime
from app.db import get_db
from app.models import User
from app.security import decode_access_token

router = APIRouter(tags=["realtime"])

AUTH_FAILED = 4401
IDLE_CLOSE = 1001


async def send_pings(websocket: WebSocket) -> None:
    try:
        while True:
            await asyncio.sleep(realtime.PING_SECONDS)
            await websocket.send_json({"type": "ping"})
    except Exception:
        return


@router.websocket("/ws")
async def live(websocket: WebSocket, token: str = Query(""), db: Session = Depends(get_db)):
    await websocket.accept()
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
        expires_at = float(payload["exp"])
    except (jwt.PyJWTError, ValueError, KeyError):
        await websocket.close(code=AUTH_FAILED)
        return

    user = db.get(User, user_id)
    db.close()
    if user is None:
        await websocket.close(code=AUTH_FAILED)
        return

    realtime.manager.add(websocket, user_id)
    heartbeat = asyncio.create_task(send_pings(websocket))
    try:
        await websocket.send_json({"type": "connected"})
        while True:
            token_left = expires_at - time.time()
            timeout = min(realtime.IDLE_TIMEOUT, token_left)
            if timeout <= 0:
                await websocket.close(code=AUTH_FAILED)
                break
            try:
                message = await asyncio.wait_for(websocket.receive(), timeout)
            except asyncio.TimeoutError:
                expired = time.time() >= expires_at
                await websocket.close(code=AUTH_FAILED if expired else IDLE_CLOSE)
                break
            if message["type"] == "websocket.disconnect":
                break
    except Exception:
        pass
    finally:
        heartbeat.cancel()
        realtime.manager.remove(websocket)
