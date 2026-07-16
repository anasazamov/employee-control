"""Tracking-modul testlari (reja §19):
- ingestion idempotentligi (offline-bufer qayta yuborsa dublikat yo'q);
- obyekt-rezolyutsiya gisterezisi (enter 2 fix, exit >=120 s, dwell hisobi);
- cross-tenant ko'rinmaslik (API + DB + pub/sub kanal-izolyatsiyasi).

Talab: docker compose dev (db 5433 + redis 6380).
"""

import json
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import func, select

from app.db import tenant_session
from app.main import app
from app.models import LocationPoint, Site, SitePresence
from app.modules.tracking import keys
from app.redis import get_redis
from tests.conftest import auth_header

# Toshkent markazi — test-obyekt geofence markazi
SITE_LAT, SITE_LON = 41.3111, 69.2797
FAR_LAT, FAR_LON = 41.2000, 69.1000  # ~15 km uzoqda


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def _pt(ts: datetime, lat: float, lon: float, accuracy_m: float | None = 100.0) -> dict:
    return {
        "point_uuid": str(uuid.uuid4()),
        "ts": ts.isoformat(),
        "lat": lat,
        "lon": lon,
        "accuracy_m": accuracy_m,
    }


async def _make_site(org_id: uuid.UUID, name: str = "Obyekt 14") -> uuid.UUID:
    async with tenant_session(org_id) as s:
        site = Site(
            org_id=org_id,
            name=name,
            center=f"SRID=4326;POINT({SITE_LON} {SITE_LAT})",
            radius_m=150,
        )
        s.add(site)
        await s.flush()
        return site.id


async def test_ingest_idempotent(seed):
    base = datetime.now(UTC) - timedelta(minutes=30)
    p1 = _pt(base, FAR_LAT, FAR_LON)
    p2 = _pt(base + timedelta(seconds=30), FAR_LAT, FAR_LON)
    batch = {"points": [p1, p2]}
    my_uuids = [uuid.UUID(p1["point_uuid"]), uuid.UUID(p2["point_uuid"])]

    async with _client() as c:
        r1 = await c.post("/v1/locations/batch", json=batch, headers=auth_header(seed.org1))
        assert r1.status_code == 200, r1.text
        assert r1.json() == {"accepted": 2, "duplicates": 0, "current_site_id": None}

        # Xuddi shu batch qayta (offline-bufer retry ssenariysi)
        r2 = await c.post("/v1/locations/batch", json=batch, headers=auth_header(seed.org1))
        assert r2.json()["accepted"] == 0
        assert r2.json()["duplicates"] == 2

    # O'z nuqtalariga cheklangan (shared-seed DB: boshqa testlar ham nuqta qo'shadi)
    async with tenant_session(seed.org1.org_id) as s:
        n = await s.scalar(
            select(func.count())
            .select_from(LocationPoint)
            .where(LocationPoint.point_uuid.in_(my_uuids))
        )
    assert n == 2


async def test_last_locations_rbac_and_tenant_scope(seed):
    async with _client() as c:
        # org1 admin o'z xodimini ko'radi
        r = await c.get("/v1/locations/last", headers=auth_header(seed.org1))
        pts = r.json()["points"]
        assert len(pts) == 1
        assert pts[0]["user_id"] == str(seed.org1.owner_id)

        # org2 admin org1 nuqtalarini KO'RMAYDI (kalit-prefiks izolyatsiyasi)
        r = await c.get("/v1/locations/last", headers=auth_header(seed.org2))
        assert r.json()["points"] == []

    # DB darajasida ham (RLS)
    async with tenant_session(seed.org2.org_id) as s:
        n = await s.scalar(select(func.count()).select_from(LocationPoint))
    assert n == 0


async def test_site_presence_enter_exit_hysteresis(seed):
    site_id = await _make_site(seed.org1.org_id)
    base = datetime.now(UTC) - timedelta(minutes=20)
    hdr = auth_header(seed.org1)

    # org1 kanaliga obuna — hodisalar publish bo'lishini ham tekshiramiz
    pubsub = get_redis().pubsub()
    await pubsub.subscribe(keys.live_channel(seed.org1.org_id))
    # subscribe-tasdiq xabarini yutamiz — aks holda drain() birinchi chaqiriqda
    # uni "ignore" qilib None ko'radi va data-xabarlarga yetmasdan tugaydi
    await pubsub.get_message(timeout=1.0)

    async def drain() -> list[dict]:
        out = []
        while True:
            m = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.5)
            if m is None:
                return out
            out.append(json.loads(m["data"]))

    async with _client() as c:
        async def send(ts, lat, lon, acc=100.0):
            r = await c.post(
                "/v1/locations/batch", json={"points": [_pt(ts, lat, lon, acc)]}, headers=hdr
            )
            assert r.status_code == 200, r.text
            return r.json()

        # 1-ichki fix (acc=100 > radius/2=75 → darhol enter YO'Q — gisterezis)
        res = await send(base, SITE_LAT, SITE_LON)
        assert res["current_site_id"] is None
        r = await c.get(f"/v1/sites/{site_id}/occupants", headers=hdr)
        assert r.json() == []

        # 2-ketma-ket ichki fix → ENTER
        res = await send(base + timedelta(seconds=30), SITE_LAT, SITE_LON)
        assert res["current_site_id"] == str(site_id)
        r = await c.get(f"/v1/sites/{site_id}/occupants", headers=hdr)
        occ = r.json()
        assert len(occ) == 1 and occ[0]["user_id"] == str(seed.org1.owner_id)

        events = await drain()
        assert any(e["type"] == "site_enter" and e["site_id"] == str(site_id) for e in events)

        # Tashqariga chiqdi — hali exit emas (120 s o'tmagan)
        res = await send(base + timedelta(seconds=60), FAR_LAT, FAR_LON)
        assert res["current_site_id"] == str(site_id)

        # 120+ s tashqarida → EXIT. Chiqish vaqti = birinchi tashqi fix (60 s),
        # dwell = enter(30s)..out_since(60s) = 30 s (konservativ, anti-fraud foydasiga)
        res = await send(base + timedelta(seconds=240), FAR_LAT, FAR_LON)
        assert res["current_site_id"] is None
        r = await c.get(f"/v1/sites/{site_id}/occupants", headers=hdr)
        assert r.json() == []

        events = await drain()
        exits = [e for e in events if e["type"] == "site_exit"]
        assert len(exits) == 1
        assert exits[0]["dwell_seconds"] == 30

        # last-loc'da site_id endi None, oxirgi koordinata FAR
        r = await c.get("/v1/locations/last", headers=hdr)
        me = next(p for p in r.json()["points"] if p["user_id"] == str(seed.org1.owner_id))
        assert me["site_id"] is None

    # DB'da yopiq davr to'g'ri yozilgan (o'z obyektiga cheklangan — shared-seed DB)
    async with tenant_session(seed.org1.org_id) as s:
        sp = (
            await s.scalars(select(SitePresence).where(SitePresence.site_id == site_id))
        ).all()
    assert len(sp) == 1
    assert sp[0].dwell_seconds == 30
    assert sp[0].exited_at is not None

    await pubsub.unsubscribe()
    await pubsub.aclose()


async def test_out_of_order_batch_does_not_regress_state(seed):
    """Kechikkan (eski ts'li) batch: DB'ga yoziladi (dalil), lekin last-loc va
    gisterezis-holat orqaga sakramaydi."""
    hdr = auth_header(seed.org1)
    async with _client() as c:
        r = await c.get("/v1/locations/last", headers=hdr)
        before = next(
            p for p in r.json()["points"] if p["user_id"] == str(seed.org1.owner_id)
        )

        old_ts = datetime.now(UTC) - timedelta(hours=2)
        r = await c.post(
            "/v1/locations/batch",
            json={"points": [_pt(old_ts, 40.0, 68.0)]},
            headers=hdr,
        )
        assert r.status_code == 200, r.text
        assert r.json()["accepted"] == 1  # dalil sifatida saqlandi

        r = await c.get("/v1/locations/last", headers=hdr)
        after = next(
            p for p in r.json()["points"] if p["user_id"] == str(seed.org1.owner_id)
        )
    # last-loc eski nuqta bilan QAYTA YOZILMAGAN
    assert after["ts"] == before["ts"]
    assert after["lat"] == before["lat"]


async def test_pubsub_channel_isolation(seed):
    """org1'dagi ingestion org2 kanaliga HEch narsa publish qilmaydi."""
    r = get_redis()
    ps2 = r.pubsub()
    await ps2.subscribe(keys.live_channel(seed.org2.org_id))
    await ps2.get_message(timeout=1.0)  # subscribe-tasdiqni yutish

    async with _client() as c:
        await c.post(
            "/v1/locations/batch",
            json={"points": [_pt(datetime.now(UTC), FAR_LAT, FAR_LON)]},
            headers=auth_header(seed.org1),
        )

    msg = await ps2.get_message(ignore_subscribe_messages=True, timeout=1.0)
    assert msg is None

    await ps2.unsubscribe()
    await ps2.aclose()


async def test_sites_crud_and_rbac(seed):
    async with _client() as c:
        # field_employee yaratolmaydi
        r = await c.post(
            "/v1/sites",
            json={"name": "X", "lat": 41.0, "lon": 69.0},
            headers=auth_header(seed.org1, role="field_employee"),
        )
        assert r.status_code == 403

        r = await c.post(
            "/v1/sites",
            json={"name": "Yangi obyekt", "lat": 41.35, "lon": 69.30, "radius_m": 200},
            headers=auth_header(seed.org1),
        )
        assert r.status_code == 201, r.text
        sid = r.json()["id"]
        assert abs(r.json()["lat"] - 41.35) < 1e-6

        # org2 bu obyektni ko'rmaydi (RLS)
        r = await c.get(f"/v1/sites/{sid}", headers=auth_header(seed.org2))
        assert r.status_code == 404

        r = await c.patch(
            f"/v1/sites/{sid}", json={"radius_m": 300}, headers=auth_header(seed.org1)
        )
        assert r.json()["radius_m"] == 300
        assert abs(r.json()["lat"] - 41.35) < 1e-6  # koordinata o'zgarmagan


def test_ws_route_registered():
    # app.routes lazy _IncludedRouter'larni yoymaydi — marshrutni manbada tekshiramiz;
    # jonli ulanish scripts/ws_smoke.py bilan tekshiriladi
    from app.modules.tracking.ws import router as ws_router

    assert any(getattr(r, "path", None) == "/v1/live" for r in ws_router.routes)


async def test_ingest_requires_auth(seed):
    async with _client() as c:
        r = await c.post(
            "/v1/locations/batch",
            json={"points": [_pt(datetime.now(UTC), 41.0, 69.0)]},
        )
        assert r.status_code in (401, 403)


# Eslatma: to'liq WS-mijoz testi (snapshot + jonli hodisa) pytest'dan tashqarida
# scripts/ws_smoke.py bilan jonli uvicorn'da tekshiriladi — httpx WS'ni qo'llamaydi,
# sync TestClient esa loop-bog'langan global mijozlar bilan to'qnashadi.
