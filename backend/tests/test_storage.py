"""Selfie-yuklash end-to-end (haqiqiy MinIO :9000 — infra/docker-compose.dev).

Presigned PUT → real HTTP PUT → check-in'ga selfie_key biriktirish → presigned GET."""

import uuid
from datetime import UTC, datetime

import httpx

from app.db import tenant_session
from app.main import app
from app.models import Checkin
from tests.conftest import auth_header


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_selfie_upload_and_attach(seed):
    hdr = auth_header(seed.org1)
    async with _client() as c:
        # 1) presigned PUT olamiz
        r = await c.post("/v1/checkins/selfie-url", headers=hdr)
        assert r.status_code == 200, r.text
        presign = r.json()
        assert presign["object_key"].startswith(f"checkins/{seed.org1.owner_id}/")
        assert presign["bucket"] == f"t-{seed.org1.org_id}"

    # 2) haqiqiy PUT — MinIO'ga to'g'ridan (presigned URL localhost:9000)
    async with httpx.AsyncClient() as raw:
        put = await raw.put(presign["url"], content=b"\xff\xd8\xff fake-jpeg-bytes")
        assert put.status_code == 200, put.text

    cid = uuid.uuid4()
    async with _client() as c:
        # 3) check-in — selfie_key biriktiriladi
        r = await c.post(
            "/v1/checkins",
            json={
                "checkin_id": str(cid),
                "ts": datetime.now(UTC).isoformat(),
                "lat": 41.0,
                "lon": 69.0,
                "selfie_key": presign["object_key"],
                "face": {},
                "device_integrity": {},
            },
            headers=hdr,
        )
        assert r.status_code == 200, r.text

        # 4) selfie-ko'rish URL (review-navbat) + access-log
        r = await c.get(f"/v1/checkins/{cid}/selfie-url", headers=hdr)
        assert r.status_code == 200, r.text
        assert r.json()["url"].startswith("http")

    async with tenant_session(seed.org1.org_id) as s:
        ck = await s.get(Checkin, cid)
    assert ck.selfie_key == presign["object_key"]


async def test_foreign_selfie_key_rejected(seed):
    """Boshqa xodim/tenant prefiksidagi kalit biriktirilmaydi (jim tashlanadi)."""
    hdr = auth_header(seed.org1)
    cid = uuid.uuid4()
    async with _client() as c:
        r = await c.post(
            "/v1/checkins",
            json={
                "checkin_id": str(cid),
                "ts": datetime.now(UTC).isoformat(),
                "lat": 41.0,
                "lon": 69.0,
                "selfie_key": "checkins/00000000-0000-0000-0000-000000000000/evil.jpg",
                "face": {},
                "device_integrity": {},
            },
            headers=hdr,
        )
        assert r.status_code == 200, r.text

    async with tenant_session(seed.org1.org_id) as s:
        ck = await s.get(Checkin, cid)
    assert ck.selfie_key is None  # begona kalit qabul qilinmadi
