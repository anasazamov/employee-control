"""Aktivatsiya oqimi end-to-end (API darajasida):
invite resolve → OTP so'rash (dev-kod) → activate → JWT bilan /v1/me.
"""

import httpx
from sqlalchemy import select

from app.db import tenant_session
from app.main import app
from app.models import Device


async def _client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_full_activation_flow(seed):
    async with await _client() as client:
        # 1) invite resolve — org yuzdan (va OTP'dan) OLDIN aniqlanadi
        r = await client.post("/v1/auth/invites/resolve", json={"token": seed.org1.invite_token})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["org_id"] == str(seed.org1.org_id)
        assert body["org_name"] == "Test Org 1"
        assert "*" in body["masked_phone"]

        # 2) OTP (dev-rejimda kod javobda qaytadi; prod'da faqat SMS)
        r = await client.post("/v1/auth/otp/request", json={"token": seed.org1.invite_token})
        assert r.status_code == 200, r.text
        dev_code = r.json()["dev_code"]
        assert dev_code and len(dev_code) == 6

        # 3) aktivatsiya → qurilma-bog'lash + JWT juftligi
        r = await client.post(
            "/v1/auth/activate",
            json={
                "token": seed.org1.invite_token,
                "otp_code": dev_code,
                "device": {"platform": "android", "fingerprint": "test-fp-1", "model": "Pixel"},
            },
        )
        assert r.status_code == 200, r.text
        tokens = r.json()
        assert tokens["user"]["org_id"] == str(seed.org1.org_id)

        # 4) himoyalangan endpoint token bilan ishlaydi
        r = await client.get(
            "/v1/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )
        assert r.status_code == 200, r.text
        me = r.json()
        assert me["role"] == "org_admin"
        assert me["org_id"] == str(seed.org1.org_id)

        # 5) invite qayta ishlatilmaydi
        r = await client.post("/v1/auth/otp/request", json={"token": seed.org1.invite_token})
        assert r.status_code == 400

    # qurilma bog'langan va faol
    async with tenant_session(seed.org1.org_id) as s:
        devices = (await s.scalars(select(Device))).all()
    assert len(devices) == 1
    assert devices[0].status == "active"
    assert devices[0].fingerprint == "test-fp-1"


async def test_invalid_token_rejected(seed):
    async with await _client() as client:
        r = await client.post("/v1/auth/invites/resolve", json={"token": "notogri-token"})
        assert r.status_code == 400

        r = await client.get("/v1/me", headers={"Authorization": "Bearer yaroqsiz"})
        assert r.status_code == 401
