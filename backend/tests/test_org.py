"""Bo'limlar/xodimlar/tarix testlari (reja §10, §12, §14, §19)."""

import io
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import func, select

from app.db import tenant_session
from app.geo import point_ewkt
from app.main import app
from app.models import AccessLog, LocationPoint, Site, SitePresence
from tests.conftest import auth_header


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_department_tree_and_delete_guard(seed):
    async with _client() as c:
        hdr = auth_header(seed.org1)
        # ildiz-bo'lim ostida (provision org-ildizida haqiqiy bo'lim yaratadi)
        r = await c.post("/v1/departments", json={"name": "Toshkent boshqarma"}, headers=hdr)
        assert r.status_code == 201, r.text
        parent = r.json()
        assert parent["path"].startswith("o_test_org_1.")
        root_id = parent["parent_id"]  # ildiz-bo'limning UUID'si (None emas)
        assert root_id is not None

        # ichki bo'lim
        r = await c.post(
            "/v1/departments",
            json={"name": "Inspeksiya 2", "parent_id": parent["id"]},
            headers=hdr,
        )
        assert r.status_code == 201, r.text
        child = r.json()
        assert child["path"].startswith(parent["path"] + ".")
        assert child["parent_id"] == parent["id"]

        # list create bilan izchil: parent'ning parent_id'si o'sha root_id
        r = await c.get("/v1/departments", headers=hdr)
        by_id = {d["id"]: d for d in r.json()}
        assert by_id[parent["id"]]["parent_id"] == root_id
        assert by_id[child["id"]]["parent_id"] == parent["id"]

        # bo'sh bo'lmagan ota-bo'limni o'chirish taqiqlanadi
        r = await c.delete(f"/v1/departments/{parent['id']}", headers=hdr)
        assert r.status_code == 409

        # PATCH parent_id'ni UUID qaytaradi (yo'l-satr emas) va create/list bilan izchil
        r = await c.patch(
            f"/v1/departments/{child['id']}", json={"name": "Inspeksiya 2 (yang.)"}, headers=hdr
        )
        assert r.status_code == 200, r.text
        assert r.json()["parent_id"] == parent["id"]
        r = await c.patch(f"/v1/departments/{parent['id']}", json={"name": "TB"}, headers=hdr)
        assert r.json()["parent_id"] == root_id

        # bolani o'chirish mumkin
        r = await c.delete(f"/v1/departments/{child['id']}", headers=hdr)
        assert r.status_code == 204

        # field_employee bo'lim yaratolmaydi (RBAC)
        r = await c.post(
            "/v1/departments",
            json={"name": "X"},
            headers=auth_header(seed.org1, role="field_employee"),
        )
        assert r.status_code == 403


async def test_user_create_invite_and_phone_uniqueness(seed):
    async with _client() as c:
        hdr = auth_header(seed.org1)
        r = await c.post(
            "/v1/users",
            json={"full_name": "Alisher Karimov", "phone": "+998911112233"},
            headers=hdr,
        )
        assert r.status_code == 201, r.text
        uid = r.json()["id"]

        # bir xil telefon → 409 (tenant-ichi unikal)
        r = await c.post(
            "/v1/users",
            json={"full_name": "Boshqa", "phone": "+998911112233"},
            headers=hdr,
        )
        assert r.status_code == 409

        # org2'da bir xil telefon MUMKIN (pudratchi keysi)
        r = await c.post(
            "/v1/users",
            json={"full_name": "Alisher (org2)", "phone": "+998911112233"},
            headers=auth_header(seed.org2),
        )
        assert r.status_code == 201, r.text

        # invite yaratish
        r = await c.post(f"/v1/users/{uid}/invite", headers=hdr)
        assert r.status_code == 200, r.text
        inv = r.json()
        assert len(inv["code"]) == 8 and inv["token"]

        # invite resolve orqali org to'g'ri aniqlanadi
        r = await c.post("/v1/auth/invites/resolve", json={"token": inv["token"]})
        assert r.json()["org_id"] == str(seed.org1.org_id)


async def test_csv_import_partial_success(seed):
    async with _client() as c:
        hdr = auth_header(seed.org1)
        r = await c.post("/v1/departments", json={"name": "Import bo'lim"}, headers=hdr)
        dept_path = r.json()["path"]

        csv_text = (
            "full_name,phone,role,department_path,employee_no\n"
            f"Valid One,+998900000101,field_employee,{dept_path},E-1\n"
            ",+998900000102,field_employee,,\n"  # ism bo'sh → xato
            "Dup Phone,+998900000101,field_employee,,\n"  # takror telefon → xato
            "Bad Dept,+998900000103,field_employee,o_yoq.bolim,\n"  # bo'lim yo'q → xato
            "Bad Role,+998900000104,superhero,,\n"  # noto'g'ri rol → xato
            "Valid Two,+998900000105,hr,,E-2\n"
        )
        files = {"file": ("xodimlar.csv", io.BytesIO(csv_text.encode()), "text/csv")}
        r = await c.post("/v1/users/import", files=files, headers=hdr)
        assert r.status_code == 200, r.text
        res = r.json()
        assert res["created"] == 2
        assert res["errors"] == 4
        statuses = {row["row"]: row["status"] for row in res["rows"]}
        assert statuses[2] == "created" and statuses[7] == "created"
        assert statuses[3] == statuses[4] == statuses[5] == statuses[6] == "error"

    # DB'da aynan 2 ta yangi (org1 owner'i + 2 = 3, lekin boshqa testlar ham qo'shishi
    # mumkin — shuning uchun import qilinganini nomi bo'yicha tekshiramiz)
    async with tenant_session(seed.org1.org_id) as s:
        from app.models import User

        names = set(
            (
                await s.scalars(
                    select(User.full_name).where(User.full_name.in_(["Valid One", "Valid Two"]))
                )
            ).all()
        )
    assert names == {"Valid One", "Valid Two"}


async def test_csv_import_overlong_value_is_row_error_not_500(seed):
    """DataError (juda uzun qiymat) qismli-muvaffaqiyatni buzmasligi kerak:
    yaxshi qatorlar saqlanadi, yomon qator — qator-xatosi (500 emas)."""
    async with _client() as c:
        hdr = auth_header(seed.org1)
        long_phone = "+" + "9" * 40  # phone String(20) dan uzun → DataError
        csv_text = (
            "full_name,phone\n"
            "Yaxshi Qator,+998900000301\n"
            f"Uzun Telefon,{long_phone}\n"
            "Yana Yaxshi,+998900000302\n"
        )
        files = {"file": ("x.csv", io.BytesIO(csv_text.encode()), "text/csv")}
        r = await c.post("/v1/users/import", files=files, headers=hdr)
        assert r.status_code == 200, r.text  # 500 EMAS
        res = r.json()
        assert res["created"] == 2  # ikkala yaxshi qator saqlandi
        assert res["errors"] == 1
        bad = next(row for row in res["rows"] if row["status"] == "error")
        assert "uzun" in bad["detail"]

    async with tenant_session(seed.org1.org_id) as s:
        from app.models import User

        names = set(
            (
                await s.scalars(
                    select(User.full_name).where(
                        User.full_name.in_(["Yaxshi Qator", "Yana Yaxshi"])
                    )
                )
            ).all()
        )
    assert names == {"Yaxshi Qator", "Yana Yaxshi"}


async def test_track_history_and_access_log(seed):
    # Ma'lumot: lokatsiya nuqtalari + check-in + presence
    org_id = seed.org1.org_id
    uid = seed.org1.owner_id
    base = datetime.now(UTC) - timedelta(hours=1)

    async with tenant_session(org_id) as s:
        site = Site(org_id=org_id, name="Tarix obyekt", center=point_ewkt(lat=41.31, lon=69.28))
        s.add(site)
        await s.flush()
        # 3 nuqta: 2 tasi bir joyda (to'xtash), keyin katta bo'shliq
        pts = [
            (base, 41.31, 69.28),
            (base + timedelta(minutes=6), 41.31, 69.28),  # ~6 daq turdi → stop
            (base + timedelta(minutes=40), 41.35, 69.30),  # 34 daq bo'shliq → gap
        ]
        for ts, lat, lon in pts:
            s.add(
                LocationPoint(
                    ts=ts,
                    point_uuid=uuid.uuid4(),
                    org_id=org_id,
                    user_id=uid,
                    geog=point_ewkt(lat=lat, lon=lon),
                    accuracy_m=10,
                )
            )
        s.add(
            SitePresence(
                org_id=org_id,
                user_id=uid,
                site_id=site.id,
                entered_at=base,
                exited_at=base + timedelta(minutes=30),
                dwell_seconds=1800,
            )
        )

    async with _client() as c:
        r = await c.get(
            f"/v1/employees/{uid}/track",
            params={
                "ts_from": (base - timedelta(minutes=5)).isoformat(),
                "ts_to": (base + timedelta(hours=1)).isoformat(),
                "stop_min_seconds": 300,
            },
            headers=auth_header(seed.org1),
        )
        assert r.status_code == 200, r.text
        out = r.json()
        assert len(out["points"]) == 3
        assert len(out["stops"]) == 1  # birinchi 2 nuqta ~6 daq
        assert len(out["gaps"]) == 1  # 34 daq bo'shliq
        assert out["gaps"][0]["seconds"] > 15 * 60

        r = await c.get(
            f"/v1/employees/{uid}/timeline",
            params={
                "ts_from": (base - timedelta(minutes=5)).isoformat(),
                "ts_to": (base + timedelta(hours=1)).isoformat(),
            },
            headers=auth_header(seed.org1),
        )
        seg = r.json()
        assert len(seg) == 1
        assert seg[0]["site_name"] == "Tarix obyekt"
        assert seg[0]["dwell_seconds"] == 1800

    # access_log: track + timeline ko'rish yozildi (kuzatuvchini kuzatish)
    async with tenant_session(org_id) as s:
        n = await s.scalar(
            select(func.count())
            .select_from(AccessLog)
            .where(AccessLog.subject_id == uid, AccessLog.resource.in_(["track", "timeline"]))
        )
    assert n >= 2


async def test_track_cross_tenant_blocked(seed):
    async with _client() as c:
        # org2 admin org1 xodimining tarixini ko'rolmaydi
        r = await c.get(
            f"/v1/employees/{seed.org1.owner_id}/track",
            params={
                "ts_from": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
                "ts_to": datetime.now(UTC).isoformat(),
            },
            headers=auth_header(seed.org2),
        )
        assert r.status_code == 404
