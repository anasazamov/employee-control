"""Yuz-verifikatsiya testlari (reja §6, §19) — StubEmbedder bilan.

Stub deterministik: bir xil bayt → bir xil vektor (cosine 1.0), turli bayt →
deyarli ortogonal (cosine ~0). Shu bilan enroll/verify/identify/dedup va check-in
server-verifikatsiya oqimi to'liq sinaladi. Haqiqiy model (insightface) deploy'da.
"""

import uuid
from datetime import UTC, datetime

import httpx
import pytest

from app.db import tenant_session
from app.main import app
from app.models import User
from app.modules.auth.security import issue_token
from app.modules.face import service as face
from tests.conftest import auth_header


def img(seed: str) -> bytes:
    """Deterministik, farqli 'rasm' baytlari (stub uchun yetarli)."""
    return f"IMG::{seed}::{'x' * 32}".encode()


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def _mk_user(org_id: uuid.UUID, name: str) -> uuid.UUID:
    async with tenant_session(org_id) as s:
        u = User(
            org_id=org_id, full_name=name, phone="+99890" + uuid.uuid4().hex[:7],
            role="field_employee",
        )
        s.add(u)
        await s.flush()
        return u.id


async def test_enroll_verify_identify_dedup_service(seed):
    org_id = seed.org1.org_id
    u1 = await _mk_user(org_id, "Yuz U1")
    u2 = await _mk_user(org_id, "Yuz U2")

    async with tenant_session(org_id) as s:
        await face.enroll(s, org_id=org_id, user_id=u1, image_bytes=img("u1"))
        await face.enroll(s, org_id=org_id, user_id=u2, image_bytes=img("u2"))

    async with tenant_session(org_id) as s:
        # 1:1 verify — o'sha yuz → verified (cosine ~1.0)
        r = await face.verify(s, user_id=u1, image_bytes=img("u1"))
        assert r.verdict == "verified" and r.score > 0.99

        # boshqa yuz → rejected (cosine past)
        r = await face.verify(s, user_id=u1, image_bytes=img("boshqa-odam"))
        assert r.verdict == "rejected" and r.score < 0.30

        # ro'yxatga olinmagan xodim → no_enrollment
        u3 = await _mk_user(org_id, "Yuz U3")
        r = await face.verify(s, user_id=u3, image_bytes=img("u3"))
        assert r.verdict == "no_enrollment"

        # 1:N identify — u1 yuzi → u1 topiladi (chegara+margin)
        r = await face.identify(s, image_bytes=img("u1"))
        assert r.user_id == str(u1) and r.score > 0.99

        # notanish yuz → hech kim (past ball)
        r = await face.identify(s, image_bytes=img("umuman-notanish"))
        assert r.user_id is None

        # dedup: u3'ni u1 yuzi bilan ro'yxatga olish → bloklanadi
        with pytest.raises(face.DuplicateFaceError) as e:
            await face.enroll(s, org_id=org_id, user_id=u3, image_bytes=img("u1"))
        assert e.value.other_user_id == u1


async def test_enroll_endpoint_rbac_and_dup(seed):
    org_id = seed.org1.org_id
    emp = await _mk_user(org_id, "Enroll Endpoint")
    async with _client() as c:
        # field_employee enroll qila olmaydi (HR-marosimi)
        r = await c.post(
            f"/v1/users/{emp}/face/enroll",
            files={"file": ("f.jpg", img("emp-a"), "image/jpeg")},
            headers=auth_header(seed.org1, role="field_employee"),
        )
        assert r.status_code == 403

        # HR/admin enroll qiladi
        r = await c.post(
            f"/v1/users/{emp}/face/enroll",
            files={"file": ("f.jpg", img("emp-a"), "image/jpeg")},
            headers=auth_header(seed.org1),
        )
        assert r.status_code == 200, r.text
        assert r.json()["model_ver"] == "stub-v1"

        # boshqa xodimni o'sha yuz bilan → 409 dedup
        emp2 = await _mk_user(org_id, "Enroll Dup")
        r = await c.post(
            f"/v1/users/{emp2}/face/enroll",
            files={"file": ("f.jpg", img("emp-a"), "image/jpeg")},
            headers=auth_header(seed.org1),
        )
        assert r.status_code == 409


async def _emp_token(org_id: uuid.UUID, emp_id: uuid.UUID) -> dict:
    tok = issue_token(user_id=emp_id, org_id=org_id, role="field_employee", kind="access")
    return {"Authorization": f"Bearer {tok}"}


async def test_checkin_server_face_verified_then_rejected(seed):
    """End-to-end: enroll → selfie MinIO'ga → check-in server-verify."""
    org_id = seed.org1.org_id
    emp = await _mk_user(org_id, "Checkin Face")
    face_bytes = img("checkin-face-enrolled")

    async with _client() as c:
        # HR yuzni ro'yxatga oladi
        r = await c.post(
            f"/v1/users/{emp}/face/enroll",
            files={"file": ("f.jpg", face_bytes, "image/jpeg")},
            headers=auth_header(seed.org1),
        )
        assert r.status_code == 200, r.text

        eh = await _emp_token(org_id, emp)

        # 1) TO'G'RI yuz: selfie = ro'yxatdagi bayt → verified
        r = await c.post("/v1/checkins/selfie-url", headers=eh)
        presign = r.json()
        async with httpx.AsyncClient() as raw:
            await raw.put(presign["url"], content=face_bytes)
        r = await c.post(
            "/v1/checkins",
            json={
                "checkin_id": str(uuid.uuid4()),
                "ts": datetime.now(UTC).isoformat(),
                "lat": 41.0, "lon": 69.0,
                "selfie_key": presign["object_key"],
                "face": {}, "device_integrity": {},
            },
            headers=eh,
        )
        assert r.status_code == 200, r.text
        ok = r.json()
        assert ok["verdict"] == "verified"
        assert ok["server_face_score"] > 0.99
        assert "server_face_rejected" not in ok["verdict_reasons"]

        # 2) BOSHQA yuz: selfie ≠ ro'yxatdagi → rejected
        r = await c.post("/v1/checkins/selfie-url", headers=eh)
        presign2 = r.json()
        async with httpx.AsyncClient() as raw:
            await raw.put(presign2["url"], content=img("firibgar-yuz"))
        r = await c.post(
            "/v1/checkins",
            json={
                "checkin_id": str(uuid.uuid4()),
                "ts": datetime.now(UTC).isoformat(),
                "lat": 41.0, "lon": 69.0,
                "selfie_key": presign2["object_key"],
                "face": {}, "device_integrity": {},
            },
            headers=eh,
        )
        bad = r.json()
        assert bad["verdict"] == "rejected"
        assert "server_face_rejected" in bad["verdict_reasons"]
        assert bad["server_face_score"] < 0.30


async def test_checkin_no_enrollment_flags(seed):
    """Ro'yxatga olinmagan xodim selfie bilan check-in → no_enrollment sababi."""
    org_id = seed.org1.org_id
    emp = await _mk_user(org_id, "No Enroll Checkin")
    async with _client() as c:
        eh = await _emp_token(org_id, emp)
        r = await c.post("/v1/checkins/selfie-url", headers=eh)
        presign = r.json()
        async with httpx.AsyncClient() as raw:
            await raw.put(presign["url"], content=img("nobody"))
        r = await c.post(
            "/v1/checkins",
            json={
                "checkin_id": str(uuid.uuid4()),
                "ts": datetime.now(UTC).isoformat(),
                "lat": 41.0, "lon": 69.0,
                "selfie_key": presign["object_key"],
                "face": {}, "device_integrity": {},
            },
            headers=eh,
        )
        assert r.status_code == 200, r.text
        assert "no_enrollment" in r.json()["verdict_reasons"]
