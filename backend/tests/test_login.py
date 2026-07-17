"""Username/parol login testlari (reja §19)."""

import uuid

import httpx

from app.main import app
from app.models import Organization
from tests.conftest import auth_header


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def _create_user_with_creds(org, username, password, role="field_employee"):
    async with _client() as c:
        r = await c.post(
            "/v1/users",
            json={
                "full_name": "Login User",
                "phone": "+99890" + uuid.uuid4().hex[:7],
                "role": role,
                "username": username,
                "password": password,
            },
            headers=auth_header(org),
        )
        assert r.status_code == 201, r.text
        return r.json()["id"]


async def test_login_success_and_role(seed):
    uname = "emp_" + uuid.uuid4().hex[:8]
    await _create_user_with_creds(seed.org1, uname, "secret123", role="field_employee")

    async with _client() as c:
        r = await c.post("/v1/auth/login", json={"username": uname, "password": "secret123"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["user"]["role"] == "field_employee"
        assert body["user"]["org_id"] == str(seed.org1.org_id)
        tok = body["access_token"]

        # token bilan /v1/me ishlaydi
        r = await c.get("/v1/me", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 200
        assert r.json()["role"] == "field_employee"

        # username katta-kichik harfga befarq
        r = await c.post(
            "/v1/auth/login", json={"username": uname.upper(), "password": "secret123"}
        )
        assert r.status_code == 200


async def test_login_wrong_password(seed):
    uname = "emp_" + uuid.uuid4().hex[:8]
    await _create_user_with_creds(seed.org1, uname, "correcthorse")
    async with _client() as c:
        r = await c.post("/v1/auth/login", json={"username": uname, "password": "wrong"})
        assert r.status_code == 401
        r = await c.post("/v1/auth/login", json={"username": "nobody-x", "password": "x"})
        assert r.status_code == 401


async def test_username_globally_unique(seed):
    uname = "dup_" + uuid.uuid4().hex[:8]
    await _create_user_with_creds(seed.org1, uname, "pass123")
    async with _client() as c:
        # org2'da ham xuddi shu username → 409 (global-unikal)
        r = await c.post(
            "/v1/users",
            json={
                "full_name": "Other", "phone": "+998911234567",
                "username": uname, "password": "pass123",
            },
            headers=auth_header(seed.org2),
        )
        assert r.status_code == 409


async def test_set_password_and_manager_role(seed):
    async with _client() as c:
        # manager (dept_head) yaratamiz, keyin parol o'rnatamiz
        r = await c.post(
            "/v1/users",
            json={"full_name": "Boss", "phone": "+998911112200", "role": "dept_head"},
            headers=auth_header(seed.org1),
        )
        uid = r.json()["id"]
        uname = "boss_" + uuid.uuid4().hex[:6]
        r = await c.post(
            f"/v1/users/{uid}/set-password",
            json={"username": uname, "password": "bosspass1"},
            headers=auth_header(seed.org1),
        )
        assert r.status_code == 204

        r = await c.post("/v1/auth/login", json={"username": uname, "password": "bosspass1"})
        assert r.status_code == 200
        assert r.json()["user"]["role"] == "dept_head"  # rol -> UI (manager rejimi)


async def test_login_blocked_when_org_suspended(seed, admin_session):
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.config import get_settings
    from app.modules.tenancy.status import invalidate_status

    uname = "susp_" + uuid.uuid4().hex[:8]
    await _create_user_with_creds(seed.org1, uname, "pass1234")

    async def set_status(status):
        url = get_settings().migrations_database_url.replace("+psycopg", "+asyncpg")
        eng = create_async_engine(url)
        try:
            async with async_sessionmaker(eng)() as s, s.begin():
                org = await s.get(Organization, seed.org1.org_id)
                org.status = status
        finally:
            await eng.dispose()
        await invalidate_status(seed.org1.org_id)

    await set_status("suspended")
    try:
        async with _client() as c:
            r = await c.post("/v1/auth/login", json={"username": uname, "password": "pass1234"})
            assert r.status_code == 401
            assert "faol emas" in r.json()["detail"]
    finally:
        await set_status("active")
