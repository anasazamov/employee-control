"""Jonli WS smoke-test: uvicorn'ga ulanib snapshot + jonli point-hodisa kelishini
tekshiradi. Ishga tushirish (server 8001-portda yurgan holda):

    python scripts/ws_smoke.py

Chiqish kodi 0 = OK. websockets kutubxonasi uvicorn[standard] bilan keladi.
"""

import asyncio
import json
import sys
import uuid
from datetime import UTC, datetime

import httpx
import websockets
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.modules.auth.security import issue_token
from app.modules.tenancy.service import provision_tenant

BASE = "http://localhost:8001"
WS = "ws://localhost:8001/v1/live"


async def main() -> int:
    url = get_settings().migrations_database_url.replace("+psycopg", "+asyncpg")
    engine = create_async_engine(url)
    try:
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as s:
            async with s.begin():
                r = await provision_tenant(
                    s, name="Demo Tashkilot", slug="demo", owner_phone="+998901234567"
                )
        org_id, owner_id = r.org.id, r.owner.id
    finally:
        await engine.dispose()

    token = issue_token(user_id=owner_id, org_id=org_id, role="org_admin", kind="access")

    async with websockets.connect(f"{WS}?token={token}") as ws:
        snapshot = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        assert snapshot["type"] == "snapshot", snapshot
        print(f"[1/2] snapshot OK ({len(snapshot['points'])} nuqta)")

        async with httpx.AsyncClient(base_url=BASE) as c:
            resp = await c.post(
                "/v1/locations/batch",
                json={
                    "points": [
                        {
                            "point_uuid": str(uuid.uuid4()),
                            "ts": datetime.now(UTC).isoformat(),
                            "lat": 41.3111,
                            "lon": 69.2797,
                            "accuracy_m": 10,
                        }
                    ]
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200, resp.text

        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            if msg["type"] == "ping":
                continue
            assert msg["type"] in ("point", "site_enter"), msg
            if msg["type"] == "point":
                assert msg["user_id"] == str(owner_id)
                print(f"[2/2] jonli point-hodisa OK (user={msg['user_id'][:8]})")
                break

    print("WS smoke: OK")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
