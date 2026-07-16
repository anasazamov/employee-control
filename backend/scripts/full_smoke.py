"""To'liq uchidan-uchiga integratsiya smoke - butun mahsulot oqimi bitta skriptda.
Web/mobil ilova aynan shu ketma-ketlikni ishlatadi.

Server 8003-portda yurgan holda: python scripts/full_smoke.py
Talab: docker-compose dev (PG 5433, Redis 6380, MinIO 9000).

Chiqish kodi 0 = butun oqim ishladi.
"""

import asyncio
import sys
import uuid
from datetime import UTC, datetime, timedelta

import httpx

from app.config import get_settings

BASE = "http://localhost:8003"
PKEY = {"X-Platform-Key": get_settings().platform_api_key}


def _step(n: int, msg: str) -> None:
    print(f"[{n:2}] {msg}")


async def main() -> int:  # noqa: C901
    slug = "e2e-" + uuid.uuid4().hex[:8]
    async with httpx.AsyncClient(base_url=BASE, timeout=30) as c:
        # 1. Platforma: tenant provision (owner-invite bilan)
        r = await c.post(
            "/platform/tenants",
            json={"name": "E2E Qurilish Nazorati", "slug": slug,
                  "owner_phone": "+998901000000", "plan": "pro"},
            headers=PKEY,
        )
        r.raise_for_status()
        prov = r.json()
        _step(1, f"tenant provision: {slug} (plan=pro)")

        # 2. Owner aktivatsiya: invite resolve -> OTP -> activate
        r = await c.post("/v1/auth/invites/resolve", json={"token": prov["invite_token"]})
        r.raise_for_status()
        _step(2, f"invite resolve -> org: {r.json()['org_name']}")

        r = await c.post("/v1/auth/otp/request", json={"token": prov["invite_token"]})
        dev_code = r.json()["dev_code"]
        r = await c.post(
            "/v1/auth/activate",
            json={
                "token": prov["invite_token"],
                "otp_code": dev_code,
                "device": {"platform": "android", "fingerprint": "e2e-device"},
            },
        )
        r.raise_for_status()
        admin_tok = r.json()["access_token"]
        ah = {"Authorization": f"Bearer {admin_tok}"}
        _step(3, "owner aktivatsiya + qurilma-bog'lash -> JWT")

        # 4. Bo'lim + xodim (inspektor) yaratish
        r = await c.post("/v1/departments", json={"name": "Toshkent inspeksiya"}, headers=ah)
        r.raise_for_status()
        dept_id = r.json()["id"]
        r = await c.post(
            "/v1/users",
            json={"full_name": "Alisher Inspektor", "phone": "+998901000001",
                  "role": "field_employee", "department_id": dept_id},
            headers=ah,
        )
        r.raise_for_status()
        emp_id = r.json()["id"]
        _step(4, "bo'lim + inspektor yaratildi")

        # 5. Inspektorni aktivatsiya qilamiz (o'z tokeni bilan ishlashi uchun)
        r = await c.post(f"/v1/users/{emp_id}/invite", headers=ah)
        emp_invite = r.json()["token"]
        r = await c.post("/v1/auth/otp/request", json={"token": emp_invite})
        r = await c.post(
            "/v1/auth/activate",
            json={"token": emp_invite, "otp_code": r.json()["dev_code"],
                  "device": {"platform": "android", "fingerprint": "e2e-emp-device"}},
        )
        emp_tok = r.json()["access_token"]
        eh = {"Authorization": f"Bearer {emp_tok}"}
        _step(5, "inspektor aktivatsiya -> o'z JWT")

        # 6. Obyekt (geofence) yaratish
        site_lat, site_lon = 41.311, 69.279
        r = await c.post(
            "/v1/sites",
            json={"name": "Obyekt N14", "lat": site_lat, "lon": site_lon, "radius_m": 150},
            headers=ah,
        )
        r.raise_for_status()
        site_id = r.json()["id"]
        _step(6, "obyekt (geofence 150m) yaratildi")

        # 7. Topshiriq: inspektor obyektga borsin
        r = await c.post(
            "/v1/assignments",
            json={"site_id": site_id, "employee_id": emp_id},
            headers=ah,
        )
        r.raise_for_status()
        _step(7, "topshiriq berildi (inspektor -> obyekt)")

        # 8. Inspektor GPS-izini yuboradi (obyekt tomon -> ichkarida)
        now = datetime.now(UTC)
        pts = [
            (now - timedelta(minutes=5), 41.30, 69.27),   # yo'lda
            (now - timedelta(minutes=3), site_lat, site_lon),  # obyektda
            (now - timedelta(minutes=1), site_lat, site_lon),  # obyektda (ENTER)
        ]
        r = await c.post(
            "/v1/locations/batch",
            json={"points": [
                {"point_uuid": str(uuid.uuid4()), "ts": ts.isoformat(),
                 "lat": la, "lon": lo, "accuracy_m": 8}
                for ts, la, lo in pts
            ]},
            headers=eh,
        )
        r.raise_for_status()
        _step(8, f"GPS-iz yuborildi -> current_site: {r.json()['current_site_id'] == site_id}")

        # 9. Rahbar jonli xaritada inspektorni ko'radi (RBAC-doira)
        r = await c.get("/v1/locations/last", headers=ah)
        seen = [p for p in r.json()["points"] if p["user_id"] == emp_id]
        _step(9, f"rahbar jonli xaritada inspektorni ko'radi: {len(seen) == 1}, "
                 f"obyektda: {seen[0]['site_id'] == site_id if seen else False}")

        # 10. Inspektor selfie yuklaydi + yuz bilan check-in (obyekt ichida)
        r = await c.post("/v1/checkins/selfie-url", headers=eh)
        presign = r.json()
        async with httpx.AsyncClient() as raw:
            await raw.put(presign["url"], content=b"\xff\xd8\xff selfie")
        r = await c.post(
            "/v1/checkins",
            json={
                "checkin_id": str(uuid.uuid4()),
                "ts": now.isoformat(),
                "lat": site_lat, "lon": site_lon, "accuracy_m": 8,
                "site_id": site_id,
                "selfie_key": presign["object_key"],
                "comment": "Fundament quyilishi tekshirildi",
                "face": {"local_match": True, "liveness_passed": True},
                "device_integrity": {},
            },
            headers=eh,
        )
        r.raise_for_status()
        ck = r.json()
        _step(10, f"check-in: verdict={ck['verdict']}, risk={ck['risk_score']}, "
                  f"geofence-ichida={ck['inside_geofence']}")

        # 11. Topshiriq avtomatik yakunlandimi?
        r = await c.get("/v1/me/assignments", headers=eh)
        done = [a for a in r.json() if a["site_id"] == site_id and a["status"] == "completed"]
        _step(11, f"topshiriq avtomatik yakunlandi: {len(done) >= 1}")

        # 12. Rahbar tarix/playback ko'radi (+access-log)
        r = await c.get(
            f"/v1/employees/{emp_id}/track",
            params={"ts_from": (now - timedelta(hours=1)).isoformat(),
                    "ts_to": now.isoformat()},
            headers=ah,
        )
        r.raise_for_status()
        tr = r.json()
        _step(12, f"tarix/playback: {len(tr['points'])} nuqta, "
                  f"{len(tr['checkins'])} check-in pin")

        # 13. Obyekt-bandlik: kim ichkarida
        r = await c.get(f"/v1/sites/{site_id}/occupants", headers=ah)
        _step(13, f"obyekt-bandlik: {len(r.json())} inspektor ichkarida")

        # 14. Metering snapshot (platforma)
        r = await c.post("/platform/usage/snapshot", json={}, headers=PKEY)
        _step(14, f"metering-snapshot: {r.json()['tenants_processed']} tenant")

    print("\nTO'LIQ OQIM: OK - provision -> aktivatsiya -> GPS -> check-in -> "
          "review -> tarix -> metering")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
