"""Platforma-konsol + metering testlari (reja §14, §19)."""

import uuid
from datetime import UTC, datetime

import httpx

from app.config import get_settings
from app.db import tenant_session
from app.main import app
from app.models import UsageSnapshot, User

KEY = {"X-Platform-Key": get_settings().platform_api_key}
BAD = {"X-Platform-Key": "wrong"}


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_platform_key_required(seed):
    async with _client() as c:
        r = await c.get("/platform/tenants", headers=BAD)
        assert r.status_code == 401
        r = await c.get("/platform/tenants")  # kalitsiz
        assert r.status_code == 401
        r = await c.get("/platform/tenants", headers=KEY)
        assert r.status_code == 200


async def test_provision_and_status_gate(seed):
    async with _client() as c:
        slug = "plat-" + uuid.uuid4().hex[:8]
        r = await c.post(
            "/platform/tenants",
            json={"name": "Platforma Test", "slug": slug, "owner_phone": "+998900001111",
                  "plan": "pro"},
            headers=KEY,
        )
        assert r.status_code == 201, r.text
        prov = r.json()
        assert prov["created"] and prov["invite_token"]
        org_id = prov["org_id"]

        # ro'yxatda ko'rinadi, plan pro
        r = await c.get("/platform/tenants", headers=KEY)
        row = next(t for t in r.json() if t["id"] == org_id)
        assert row["plan"] == "pro" and row["status"] == "active"

        # suspended qilamiz — org-admin yozuvi bloklanishi kerak (suspension-gate)
        r = await c.patch(f"/platform/tenants/{org_id}", json={"status": "suspended"}, headers=KEY)
        assert r.json()["status"] == "suspended"

        # yangi tenant admin tokeni bilan check-in → 403 (gate ishlaydi)
        from app.modules.auth.security import issue_token

        # owner_id'ni topamiz
        async with tenant_session(uuid.UUID(org_id)) as s:
            owner = await s.scalar(select_owner())
        tok = issue_token(
            user_id=owner.id, org_id=uuid.UUID(org_id), role="org_admin", kind="access"
        )
        r = await c.post(
            "/v1/checkins",
            json={
                "checkin_id": str(uuid.uuid4()),
                "ts": datetime.now(UTC).isoformat(),
                "lat": 41.0,
                "lon": 69.0,
                "face": {},
                "device_integrity": {},
            },
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert r.status_code == 403

        # qayta active
        r = await c.patch(f"/platform/tenants/{org_id}", json={"status": "active"}, headers=KEY)
        assert r.json()["status"] == "active"


def select_owner():
    from sqlalchemy import select

    return select(User).where(User.role == "org_admin").limit(1)


async def test_usage_snapshot(seed):
    today = datetime.now(UTC).date()
    async with _client() as c:
        r = await c.post(
            "/platform/usage/snapshot",
            json={"snapshot_date": today.isoformat()},
            headers=KEY,
        )
        assert r.status_code == 200, r.text
        assert r.json()["tenants_processed"] >= 2  # kamida seed org1+org2

        # idempotent: qayta chaqirsa xato yo'q (upsert)
        r = await c.post(
            "/platform/usage/snapshot",
            json={"snapshot_date": today.isoformat()},
            headers=KEY,
        )
        assert r.status_code == 200

    # org1 uchun snapshot yozildi va faol-xodim >= 1 (owner)
    from app.modules.platform.service import platform_session

    async with platform_session() as s:
        from sqlalchemy import select

        snap = await s.scalar(
            select(UsageSnapshot).where(
                UsageSnapshot.org_id == seed.org1.org_id,
                UsageSnapshot.snapshot_date == today,
            )
        )
    assert snap is not None
    assert snap.active_employees >= 1
