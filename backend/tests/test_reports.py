"""Anti-fraud analitika testi (reja §13, W7)."""

import uuid
from datetime import UTC, datetime, timedelta

import httpx

from app.db import tenant_session
from app.geo import point_ewkt
from app.main import app
from app.models import Assignment, Checkin, Site, SitePresence, User
from tests.conftest import auth_header

LAT, LON = 38.8610, 65.7890  # Qarshi — boshqa testlardan uzoq


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_employee_integrity_report(seed):
    org_id = seed.org1.org_id
    now = datetime.now(UTC)

    async with tenant_session(org_id) as s:
        # Alohida yangi inspektor — boshqa testlar tegmaydi (shared-seed toza hisob)
        emp = User(
            org_id=org_id,
            full_name="Analitika Inspektor",
            phone="+99890" + uuid.uuid4().hex[:7],
            role="field_employee",
        )
        s.add(emp)
        await s.flush()
        uid = emp.id
        site = Site(
            org_id=org_id, name="Qarshi obyekt", center=point_ewkt(lat=LAT, lon=LON),
            min_dwell_minutes=15,
        )
        s.add(site)
        await s.flush()
        # 2 check-in: 1 flagged, 1 pending
        s.add(Checkin(org_id=org_id, user_id=uid, ts=now, lat=LAT, lon=LON,
                      verdict="flagged", risk_score=65))
        s.add(Checkin(org_id=org_id, user_id=uid, ts=now, lat=LAT, lon=LON,
                      verdict="pending", risk_score=15))
        # 1 qisqa tashrif (5 daq < 15 daq min-dwell) → short_dwell
        s.add(SitePresence(org_id=org_id, user_id=uid, site_id=site.id,
                           entered_at=now - timedelta(minutes=5), exited_at=now,
                           dwell_seconds=300))
        # 1 o'tkazib yuborilgan topshiriq
        s.add(Assignment(org_id=org_id, site_id=site.id, employee_id=uid, status="missed"))

    async with _client() as c:
        r = await c.get(
            "/v1/reports/employee-integrity",
            params={"ts_from": (now - timedelta(days=1)).isoformat(),
                    "ts_to": (now + timedelta(minutes=1)).isoformat()},
            headers=auth_header(seed.org1),
        )
        assert r.status_code == 200, r.text
        rows = r.json()["rows"]
        me = next(row for row in rows if row["user_id"] == str(uid))
        assert me["checkins"] == 2
        assert me["flagged"] == 1
        assert me["flagged_ratio"] == 0.5
        assert me["avg_risk"] == 40.0  # (65+15)/2
        assert me["short_dwell"] == 1
        assert me["short_dwell_ratio"] == 1.0
        assert me["assignments_missed"] == 1
        # anomaliya-ball: 40*0.5 + 20*0.4 + 25*1.0 + 15*1.0 = 20+8+25+15 = 68
        assert me["anomaly_score"] == 68

        # field_employee hisobotga kira olmaydi
        r = await c.get(
            "/v1/reports/employee-integrity",
            headers=auth_header(seed.org1, role="field_employee"),
        )
        assert r.status_code == 403


async def test_integrity_cross_tenant_isolated(seed):
    async with _client() as c:
        # org2 admin faqat o'z org'ini ko'radi — org1 owner'i chiqmaydi
        r = await c.get("/v1/reports/employee-integrity", headers=auth_header(seed.org2))
        assert r.status_code == 200
        assert str(seed.org1.owner_id) not in [row["user_id"] for row in r.json()["rows"]]
