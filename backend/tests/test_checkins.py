"""Check-ins moduli testlari (reja §9, §19):
- avto obyekt-rezolyutsiya + risk-ball + idempotentlik;
- qurilma-imzo (haqiqiy P-256 kalit; buzilgan payload → 400);
- review-oqim (RBAC, audit) va dalil-ustunlarning DB-darajasida qulflanganligi;
- izoh-append; smena API.

Eslatma: bu fayl test_tracking'dan alifbo bo'yicha OLDIN yuradi — obyektlar
Toshkent-koordinatalaridan uzoqda (Samarqand atrofi) yaratiladi, interferensiya yo'q.
"""

import base64
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import select, text

from app.db import tenant_session
from app.geo import point_ewkt
from app.main import app
from app.models import AuditLog, Device, Site
from app.modules.checkins.signing import canonical_payload
from tests.conftest import auth_header

SITE_LAT, SITE_LON = 39.6542, 66.9597  # Samarqand — tracking-testlardan uzoq
FAR_LAT, FAR_LON = 38.5000, 65.5000


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def _make_site(org_id: uuid.UUID, name: str = "Samarqand obyekt") -> uuid.UUID:
    async with tenant_session(org_id) as s:
        site = Site(
            org_id=org_id,
            name=name,
            center=point_ewkt(lat=SITE_LAT, lon=SITE_LON),
            radius_m=150,
        )
        s.add(site)
        await s.flush()
        return site.id


def _body(
    lat: float,
    lon: float,
    *,
    checkin_id: uuid.UUID | None = None,
    comment: str | None = "Fundament tekshirildi",
    integrity: dict | None = None,
    ts: datetime | None = None,
) -> dict:
    return {
        "checkin_id": str(checkin_id or uuid.uuid4()),
        "ts": (ts or datetime.now(UTC)).isoformat(),
        "lat": lat,
        "lon": lon,
        "accuracy_m": 10.0,
        "comment": comment,
        "face": {"local_match": True, "local_score": 0.71, "liveness_passed": True},
        "device_integrity": integrity or {},
    }


async def test_checkin_auto_site_and_pending(seed):
    site_id = await _make_site(seed.org1.org_id)
    async with _client() as c:
        r = await c.post(
            "/v1/checkins", json=_body(SITE_LAT, SITE_LON), headers=auth_header(seed.org1)
        )
        assert r.status_code == 200, r.text
        out = r.json()
    assert out["site_id"] == str(site_id)
    assert out["inside_geofence"] is True
    # imzosiz (unsigned=15) — chegaradan past → pending; avto-'verified' YO'Q
    assert out["verdict"] == "pending"
    assert out["verdict_reasons"] == ["unsigned"]
    assert out["risk_score"] == 15
    assert out["duplicate"] is False


async def test_checkin_idempotent(seed):
    cid = uuid.uuid4()
    body = _body(SITE_LAT, SITE_LON, checkin_id=cid)
    async with _client() as c:
        r1 = await c.post("/v1/checkins", json=body, headers=auth_header(seed.org1))
        r2 = await c.post("/v1/checkins", json=body, headers=auth_header(seed.org1))
    assert r1.json()["duplicate"] is False
    assert r2.json()["duplicate"] is True
    assert r2.json()["id"] == str(cid)


async def test_mock_location_flagged_and_review_queue(seed):
    async with _client() as c:
        r = await c.post(
            "/v1/checkins",
            json=_body(FAR_LAT, FAR_LON, integrity={"is_mock": True}),
            headers=auth_header(seed.org1),
        )
        out = r.json()
        # mock(40) + no_site(10) + unsigned(15) = 65 → flagged
        assert out["verdict"] == "flagged"
        assert set(out["verdict_reasons"]) == {"mock_location", "no_site", "unsigned"}
        assert out["risk_score"] == 65

        r = await c.get("/v1/checkins/review-queue", headers=auth_header(seed.org1))
        ids = [x["id"] for x in r.json()]
        assert out["id"] in ids

        # org2 admin org1'ning navbatini KO'RMAYDI
        r = await c.get("/v1/checkins/review-queue", headers=auth_header(seed.org2))
        assert r.json() == []

        # field_employee review-queue'ga kira olmaydi
        r = await c.get(
            "/v1/checkins/review-queue",
            headers=auth_header(seed.org1, role="field_employee"),
        )
        assert r.status_code == 403


async def test_signature_verify_and_tamper(seed):
    # Haqiqiy P-256 kalit: pubkey'ni owner'ning faol qurilmasiga yozamiz
    key = ec.generate_private_key(ec.SECP256R1())
    pub_pem = (
        key.public_key()
        .public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        .decode()
    )
    async with tenant_session(seed.org1.org_id) as s:
        device = await s.scalar(
            select(Device).where(Device.user_id == seed.org1.owner_id, Device.status == "active")
        )
        assert device is not None, "auth-flow testi qurilma bog'lagan bo'lishi kerak"
        device.pubkey = pub_pem
        device_id = device.id

    hdr = auth_header(seed.org1, device_id=device_id)
    cid = uuid.uuid4()
    ts = datetime.now(UTC)
    body = _body(SITE_LAT, SITE_LON, checkin_id=cid, ts=ts)
    payload = canonical_payload(
        checkin_id=cid, ts=ts, lat=SITE_LAT, lon=SITE_LON, site_id=None, comment=body["comment"]
    )
    body["signature"] = base64.b64encode(
        key.sign(payload, ec.ECDSA(hashes.SHA256()))
    ).decode()

    async with _client() as c:
        r = await c.post("/v1/checkins", json=body, headers=hdr)
        assert r.status_code == 200, r.text
        out = r.json()
        assert "unsigned" not in out["verdict_reasons"]
        assert out["risk_score"] == 0
        assert out["verdict"] == "pending"

        # Buzilgan payload: imzo eski, izoh o'zgartirilgan → hard-reject 400
        tampered = dict(body, checkin_id=str(uuid.uuid4()), comment="O'ZGARTIRILGAN izoh")
        r = await c.post("/v1/checkins", json=tampered, headers=hdr)
        assert r.status_code == 400
        assert "imzo" in r.json()["detail"]


async def test_comment_append_and_audit(seed):
    cid = uuid.uuid4()
    async with _client() as c:
        await c.post(
            "/v1/checkins",
            json=_body(SITE_LAT, SITE_LON, checkin_id=cid, comment="Birinchi izoh"),
            headers=auth_header(seed.org1),
        )
        r = await c.post(
            f"/v1/checkins/{cid}/comment",
            json={"text": "Qo'shimcha izoh"},
            headers=auth_header(seed.org1),
        )
        assert r.status_code == 200, r.text
        assert r.json()["comment"] == "Birinchi izoh\nQo'shimcha izoh"

    async with tenant_session(seed.org1.org_id) as s:
        audit = (
            await s.scalars(
                select(AuditLog).where(
                    AuditLog.action == "checkin_comment_appended",
                    AuditLog.object_id == cid,
                )
            )
        ).all()
    assert len(audit) == 1
    assert audit[0].detail["text"] == "Qo'shimcha izoh"


async def test_review_flow_and_evidence_lock(seed):
    cid = uuid.uuid4()
    async with _client() as c:
        await c.post(
            "/v1/checkins",
            json=_body(FAR_LAT, FAR_LON, checkin_id=cid, integrity={"is_mock": True}),
            headers=auth_header(seed.org1),
        )

        # field_employee review qila olmaydi
        r = await c.post(
            f"/v1/checkins/{cid}/review",
            json={"action": "approve", "reason": "asos yo'q"},
            headers=auth_header(seed.org1, role="field_employee"),
        )
        assert r.status_code == 403

        r = await c.post(
            f"/v1/checkins/{cid}/review",
            json={"action": "reject", "reason": "mock-GPS aniqlangan, tashrif soxta"},
            headers=auth_header(seed.org1),
        )
        assert r.status_code == 200, r.text
        assert r.json()["verdict"] == "rejected"

    async with tenant_session(seed.org1.org_id) as s:
        audit = (
            await s.scalars(
                select(AuditLog).where(
                    AuditLog.action == "checkin_reviewed", AuditLog.object_id == cid
                )
            )
        ).all()
        assert len(audit) == 1 and audit[0].detail["action"] == "reject"

    # DALIL-USTUN QULFI: lifecycle-ustun (verdict) o'zgardi, lekin lat/ts kabi
    # dalil-ustunlarga app_user UPDATE qila OLMAYDI — ustun-darajali grant (0002)
    from sqlalchemy.exc import DBAPIError, ProgrammingError

    with pytest.raises((DBAPIError, ProgrammingError)) as exc_info:
        async with tenant_session(seed.org1.org_id) as s:
            await s.execute(
                text("UPDATE checkins SET lat = 0 WHERE id = :cid"), {"cid": cid}
            )
    assert "permission denied" in str(exc_info.value).lower()


async def test_shifts_crud_and_me_shift(seed):
    now = datetime.now(UTC)
    async with _client() as c:
        # field_employee yaratolmaydi
        r = await c.post(
            "/v1/shifts",
            json={
                "shifts": [
                    {
                        "user_id": str(seed.org1.owner_id),
                        "starts_at": now.isoformat(),
                        "ends_at": (now + timedelta(hours=8)).isoformat(),
                    }
                ]
            },
            headers=auth_header(seed.org1, role="field_employee"),
        )
        assert r.status_code == 403

        # noma'lum xodim → 400
        r = await c.post(
            "/v1/shifts",
            json={
                "shifts": [
                    {
                        "user_id": str(uuid.uuid4()),
                        "starts_at": now.isoformat(),
                        "ends_at": (now + timedelta(hours=8)).isoformat(),
                    }
                ]
            },
            headers=auth_header(seed.org1),
        )
        assert r.status_code == 400

        # joriy + ertangi smena
        r = await c.post(
            "/v1/shifts",
            json={
                "shifts": [
                    {
                        "user_id": str(seed.org1.owner_id),
                        "starts_at": (now - timedelta(hours=1)).isoformat(),
                        "ends_at": (now + timedelta(hours=7)).isoformat(),
                    },
                    {
                        "user_id": str(seed.org1.owner_id),
                        "starts_at": (now + timedelta(days=1)).isoformat(),
                        "ends_at": (now + timedelta(days=1, hours=8)).isoformat(),
                    },
                ]
            },
            headers=auth_header(seed.org1),
        )
        assert r.status_code == 201, r.text

        r = await c.get("/v1/me/shift", headers=auth_header(seed.org1))
        me = r.json()
        assert me["current"] is not None
        assert me["next"] is not None

        # org2'da smena yo'q
        r = await c.get("/v1/me/shift", headers=auth_header(seed.org2))
        assert r.json() == {"current": None, "next": None}
