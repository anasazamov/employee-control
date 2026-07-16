"""Jonli end-to-end smoke: departments → user → invite → CSV-import → track.
Server 8002-portda yurgan holda: python scripts/org_smoke.py"""

import asyncio
import io
import sys
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.modules.auth.security import issue_token
from app.modules.tenancy.service import provision_tenant

BASE = "http://localhost:8002"


async def main() -> int:
    url = get_settings().migrations_database_url.replace("+psycopg", "+asyncpg")
    engine = create_async_engine(url)
    try:
        maker = async_sessionmaker(engine, expire_on_commit=False)
        slug = "smoke-" + uuid.uuid4().hex[:8]
        async with maker() as s:
            async with s.begin():
                r = await provision_tenant(
                    s, name="Smoke Org", slug=slug, owner_phone="+998900000000"
                )
        org_id, owner_id = r.org.id, r.owner.id
    finally:
        await engine.dispose()

    tok = issue_token(user_id=owner_id, org_id=org_id, role="org_admin", kind="access")
    h = {"Authorization": f"Bearer {tok}"}

    async with httpx.AsyncClient(base_url=BASE) as c:
        r = await c.post("/v1/departments", json={"name": "Toshkent"}, headers=h)
        assert r.status_code == 201, r.text
        dept = r.json()
        print(f"[1] bo'lim: {dept['path']}")

        r = await c.post(
            "/v1/users",
            json={"full_name": "Test Xodim", "phone": "+998911234567", "department_id": dept["id"]},
            headers=h,
        )
        assert r.status_code == 201, r.text
        uid = r.json()["id"]
        print(f"[2] xodim: {uid}")

        r = await c.post(f"/v1/users/{uid}/invite", headers=h)
        assert r.status_code == 200, r.text
        print(f"[3] invite kodi: {r.json()['code']}")

        csv_text = (
            "full_name,phone,department_path\n"
            f"CSV Bir,+998900000201,{dept['path']}\n"
            "CSV Ikki,+998900000202,\n"
            ",+998900000203,\n"  # xato
        )
        files = {"file": ("x.csv", io.BytesIO(csv_text.encode()), "text/csv")}
        r = await c.post("/v1/users/import", files=files, headers=h)
        assert r.status_code == 200, r.text
        res = r.json()
        assert res["created"] == 2 and res["errors"] == 1, res
        print(f"[4] CSV-import: {res['created']} yaratildi, {res['errors']} xato")

        now = datetime.now(UTC)
        r = await c.get(
            f"/v1/employees/{owner_id}/track",
            params={
                "ts_from": (now - timedelta(hours=1)).isoformat(),
                "ts_to": now.isoformat(),
            },
            headers=h,
        )
        assert r.status_code == 200, r.text
        print(f"[5] track: {len(r.json()['points'])} nuqta (bo'sh — hali GPS yo'q)")

    print("ORG smoke: OK")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
