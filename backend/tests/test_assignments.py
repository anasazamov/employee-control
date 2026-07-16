"""Topshiriqlar + suspension-gate testlari (reja §5, §4, §19).

Obyektlar Namangan atrofida — boshqa test-fayllardan uzoq (shared-seed interferensiyasiz)."""

import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db import tenant_session
from app.geo import point_ewkt
from app.main import app
from app.models import Assignment, Organization, Site
from app.modules.tenancy.status import invalidate_status
from tests.conftest import auth_header

SITE_LAT, SITE_LON = 40.9983, 71.6726  # Namangan


async def _set_org_status(org_id: uuid.UUID, status: str) -> None:
    """Suspension — platforma-superuser amali (app_user'da organizations UPDATE granti yo'q)."""
    url = get_settings().migrations_database_url.replace("+psycopg", "+asyncpg")
    engine = create_async_engine(url)
    try:
        async with async_sessionmaker(engine)() as s:
            async with s.begin():
                org = await s.get(Organization, org_id)
                org.status = status
    finally:
        await engine.dispose()
    await invalidate_status(org_id)


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def _make_site(org_id: uuid.UUID, name: str) -> uuid.UUID:
    async with tenant_session(org_id) as s:
        site = Site(org_id=org_id, name=name, center=point_ewkt(lat=SITE_LAT, lon=SITE_LON))
        s.add(site)
        await s.flush()
        return site.id


async def test_assignment_crud_and_scope(seed):
    site_id = await _make_site(seed.org1.org_id, "Namangan obyekt A")
    async with _client() as c:
        hdr = auth_header(seed.org1)
        r = await c.post(
            "/v1/assignments",
            json={"site_id": str(site_id), "employee_id": str(seed.org1.owner_id)},
            headers=hdr,
        )
        assert r.status_code == 201, r.text
        a = r.json()
        assert a["site_name"] == "Namangan obyekt A"
        assert a["status"] == "pending"

        # ro'yxat
        r = await c.get("/v1/assignments", headers=hdr)
        assert a["id"] in [x["id"] for x in r.json()]

        # o'z topshiriqlari (mobil)
        r = await c.get("/v1/me/assignments", headers=hdr)
        assert a["id"] in [x["id"] for x in r.json()]

        # status o'tishi
        r = await c.patch(
            f"/v1/assignments/{a['id']}", json={"status": "cancelled"}, headers=hdr
        )
        assert r.json()["status"] == "cancelled"

        # field_employee topshiriq bera olmaydi
        r = await c.post(
            "/v1/assignments",
            json={"site_id": str(site_id), "employee_id": str(seed.org1.owner_id)},
            headers=auth_header(seed.org1, role="field_employee"),
        )
        assert r.status_code == 403

        # org2 org1 topshirig'ini ko'rmaydi
        r = await c.get("/v1/assignments", headers=auth_header(seed.org2))
        assert a["id"] not in [x["id"] for x in r.json()]


async def test_checkin_auto_completes_assignment(seed):
    site_id = await _make_site(seed.org1.org_id, "Namangan obyekt B")
    async with _client() as c:
        hdr = auth_header(seed.org1)
        r = await c.post(
            "/v1/assignments",
            json={"site_id": str(site_id), "employee_id": str(seed.org1.owner_id)},
            headers=hdr,
        )
        assignment_id = r.json()["id"]

        # obyekt ichida check-in → topshiriq avtomatik 'completed'.
        # Aniq site_id beramiz — test-obyektlar bir koordinatada, "eng yaqin"
        # noaniq bo'ladi (mobil ilova ham obyektni biladi).
        r = await c.post(
            "/v1/checkins",
            json={
                "checkin_id": str(uuid.uuid4()),
                "ts": datetime.now(UTC).isoformat(),
                "lat": SITE_LAT,
                "lon": SITE_LON,
                "accuracy_m": 10,
                "site_id": str(site_id),
                "comment": "tekshirildi",
                "face": {"local_match": True, "liveness_passed": True},
                "device_integrity": {},
            },
            headers=hdr,
        )
        assert r.status_code == 200, r.text
        assert r.json()["site_id"] == str(site_id)

    async with tenant_session(seed.org1.org_id) as s:
        a = await s.get(Assignment, uuid.UUID(assignment_id))
    assert a.status == "completed"


async def test_compliance_summary(seed):
    site_id = await _make_site(seed.org1.org_id, "Namangan obyekt C")
    async with _client() as c:
        hdr = auth_header(seed.org1)
        # 1 completed + 1 missed yaratamiz
        r = await c.post(
            "/v1/assignments",
            json={"site_id": str(site_id), "employee_id": str(seed.org1.owner_id)},
            headers=hdr,
        )
        done_id = r.json()["id"]
        await c.patch(f"/v1/assignments/{done_id}", json={"status": "completed"}, headers=hdr)
        r = await c.post(
            "/v1/assignments",
            json={"site_id": str(site_id), "employee_id": str(seed.org1.owner_id)},
            headers=hdr,
        )
        miss_id = r.json()["id"]
        await c.patch(f"/v1/assignments/{miss_id}", json={"status": "missed"}, headers=hdr)

        r = await c.get("/v1/assignments/summary", headers=hdr)
        assert r.status_code == 200, r.text
        summ = r.json()
        assert summ["total"] >= 2
        assert summ["completed"] >= 1
        assert 0.0 <= summ["completion_rate"] <= 1.0
        statuses = {row["status"] for row in summ["by_status"]}
        assert "completed" in statuses and "missed" in statuses


async def test_suspension_gate_blocks_writes_allows_reads(seed):
    """suspended tenant: check-in/tracking POST → 403; o'qish ochiq (reja §4)."""
    org_id = seed.org2.org_id
    async with _client() as c:
        hdr = auth_header(seed.org2)
        # active holatda check-in ishlaydi
        ok_body = {
            "checkin_id": str(uuid.uuid4()),
            "ts": datetime.now(UTC).isoformat(),
            "lat": SITE_LAT,
            "lon": SITE_LON,
            "accuracy_m": 10,
            "face": {"local_match": True, "liveness_passed": True},
            "device_integrity": {},
        }
        r = await c.post("/v1/checkins", json=ok_body, headers=hdr)
        assert r.status_code == 200, r.text

        # tenant'ni suspended qilamiz (platforma-superuser amali) + kesh tozalash
        await _set_org_status(org_id, "suspended")

        try:
            # yozuv bloklangan
            r = await c.post(
                "/v1/checkins",
                json={**ok_body, "checkin_id": str(uuid.uuid4())},
                headers=hdr,
            )
            assert r.status_code == 403
            assert "faol emas" in r.json()["detail"]

            r = await c.post(
                "/v1/locations/batch",
                json={
                    "points": [
                        {
                            "point_uuid": str(uuid.uuid4()),
                            "ts": datetime.now(UTC).isoformat(),
                            "lat": SITE_LAT,
                            "lon": SITE_LON,
                        }
                    ]
                },
                headers=hdr,
            )
            assert r.status_code == 403

            # o'qish ochiq qoladi (eksport uchun)
            r = await c.get("/v1/checkins", headers=hdr)
            assert r.status_code == 200
        finally:
            # holatni tiklaymiz (boshqa testlarga ta'sir qilmasin)
            await _set_org_status(org_id, "active")
