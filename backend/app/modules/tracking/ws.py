"""WS /v1/live — jonli oqim (reja §8): Redis pub/sub org-kanalidan RBAC-doiraga
filtrlangan fan-out. Ulanishda snapshot (Redis last-loc), keyin point/site_enter/
site_exit hodisalari. Kanal org-prefiksli — tenantlar-aro oqib o'tish yo'q.
Web uzilsa 10 s polling'ga tushadi (GET /v1/locations/last).

TODO(v2): visible-to'plam ulanish paytida muzlaydi — uzoq sessiyalarda davriy
qayta-hisoblash (masalan, 5 daqiqada) yoki rol-o'zgarishda majburiy uzish kerak.
"""

import json

import jwt as pyjwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.modules.rbac.deps import context_from_token, visible_user_ids
from app.modules.tracking import keys, service
from app.redis import get_redis

router = APIRouter()


@router.websocket("/v1/live")
async def live(ws: WebSocket, token: str):
    try:
        ctx = context_from_token(token)
    except pyjwt.PyJWTError:
        await ws.close(code=4401)
        return

    visible = await visible_user_ids(ctx)

    await ws.accept()
    await ws.send_text(
        json.dumps(
            {"type": "snapshot", "points": await service.last_locations(ctx.org_id, visible)}
        )
    )

    pubsub = get_redis().pubsub()
    await pubsub.subscribe(keys.live_channel(ctx.org_id))
    try:
        while True:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=5.0)
            if msg is None:
                # o'lik soketni aniqlash uchun yengil ping (send xatosi → disconnect)
                await ws.send_text('{"type":"ping"}')
                continue
            data = json.loads(msg["data"])
            if visible is None or data.get("user_id") in visible:
                await ws.send_text(msg["data"])
    except (WebSocketDisconnect, RuntimeError):
        # RuntimeError: starlette yopilgan soketga yozishda ko'taradi.
        # CancelledError ataylab ushlanmaydi — graceful-shutdown buzilmasin.
        pass
    finally:
        await pubsub.unsubscribe()
        await pubsub.aclose()
