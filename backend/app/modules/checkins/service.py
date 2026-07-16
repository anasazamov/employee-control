"""Check-in qabul va hayotsikli (reja §9).

Risk-ball v1 — kompozit signal-yig'indi; YUMSHOQ signal hech qachon qattiq
bloklamaydi (reja §9): faqat yaroqsiz IMZO hard-reject (dalil buzilgan).
Verdikt: ball >= FLAG_THRESHOLD → 'flagged' (review-navbat), aks holda 'pending'.
TODO(face-worker): server InsightFace tekshiruvi 'verified'/'rejected' qo'yadi —
ungacha avto-'verified' YO'Q (reja §6: server hukmi majburiy).
TODO(v2): trail-korroboratsiya (lokatsiya izi obyekt tomon kelganmi) va dwell-
tekshiruv site_presence bilan bog'lanadi.
"""

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models import Checkin, Device
from app.modules.checkins.schemas import CheckinIn
from app.modules.checkins.signing import canonical_payload, verify_signature
from app.modules.rbac.deps import TenantContext
from app.modules.tracking import keys
from app.redis import get_redis
from app.utils import iso_utc

RISK_WEIGHTS = {
    "mock_location": 40,
    "outside_geofence": 30,
    "ondevice_face_failed": 25,
    "stale_capture": 20,  # offline/backdate — hech qachon avto-tasdiqlanmaydi
    "clock_skew": 20,
    "unsigned": 15,
    "unverifiable_signature": 15,
    "no_site": 10,
    "gps_accuracy_poor": 10,
}
FLAG_THRESHOLD = 40
STALE_SECONDS = 10 * 60
FUTURE_SKEW_SECONDS = 2 * 60
AUTO_ATTACH_MAX_M = 1000  # obyekt berilmasa: shu masofagacha eng yaqini biriktiriladi


class SignatureError(Exception):
    """Yaroqsiz imzo — hard-reject (400)."""


@dataclass
class SiteMatch:
    site_id: uuid.UUID
    inside: bool
    distance_m: float


_SITE_BY_ID = text(
    """
    SELECT id,
           ST_Distance(center, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography)
               AS distance_m,
           (ST_DWithin(center, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, radius_m)
            OR (geom IS NOT NULL
                AND ST_Contains(geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)))) AS inside
    FROM sites WHERE id = :site_id AND status = 'active'
    """
)

_NEAREST_SITE = text(
    """
    SELECT id,
           ST_Distance(center, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography)
               AS distance_m,
           (ST_DWithin(center, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, radius_m)
            OR (geom IS NOT NULL
                AND ST_Contains(geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)))) AS inside
    FROM sites WHERE status = 'active'
    ORDER BY distance_m LIMIT 1
    """
)


async def _resolve_site(session, body: CheckinIn) -> SiteMatch | None:
    if body.site_id is not None:
        row = (
            await session.execute(
                _SITE_BY_ID, {"lat": body.lat, "lon": body.lon, "site_id": body.site_id}
            )
        ).first()
    else:
        row = (
            await session.execute(_NEAREST_SITE, {"lat": body.lat, "lon": body.lon})
        ).first()
        if row is not None and not row.inside and row.distance_m > AUTO_ATTACH_MAX_M:
            return None
    if row is None:
        return None
    return SiteMatch(site_id=row.id, inside=row.inside, distance_m=row.distance_m)


def _risk(body: CheckinIn, site: SiteMatch | None, signed: str) -> tuple[int, list[str]]:
    """signed: 'ok' | 'missing' | 'unverifiable'."""
    reasons: list[str] = []
    now = datetime.now(UTC)

    if body.device_integrity.get("is_mock"):
        reasons.append("mock_location")
    if site is None:
        reasons.append("no_site")
    elif not site.inside:
        reasons.append("outside_geofence")
    if body.face.local_match is False or body.face.liveness_passed is False:
        reasons.append("ondevice_face_failed")
    if (now - body.ts).total_seconds() > STALE_SECONDS:
        reasons.append("stale_capture")
    if (body.ts - now).total_seconds() > FUTURE_SKEW_SECONDS:
        reasons.append("clock_skew")
    if signed == "missing":
        reasons.append("unsigned")
    elif signed == "unverifiable":
        reasons.append("unverifiable_signature")
    if body.accuracy_m is not None and body.accuracy_m > 100:
        reasons.append("gps_accuracy_poor")

    return min(100, sum(RISK_WEIGHTS[r] for r in reasons)), reasons


async def create_checkin(ctx: TenantContext, body: CheckinIn) -> dict:
    async with ctx.session() as s:
        # Imzo-siyosati (signing.py docstring): yaroqsiz → SignatureError (400)
        signed = "missing"
        if body.signature is not None:
            pubkey = None
            if ctx.device_id is not None:
                device = await s.get(Device, ctx.device_id)
                pubkey = device.pubkey if device else None
            if pubkey is None:
                signed = "unverifiable"
            elif verify_signature(
                pubkey,
                canonical_payload(
                    checkin_id=body.checkin_id,
                    ts=body.ts,
                    lat=body.lat,
                    lon=body.lon,
                    site_id=body.site_id,
                    comment=body.comment,
                ),
                body.signature,
            ):
                signed = "ok"
            else:
                raise SignatureError("imzo yaroqsiz — yozuv rad etildi")

        site = await _resolve_site(s, body)
        risk_score, reasons = _risk(body, site, signed)
        verdict = "flagged" if risk_score >= FLAG_THRESHOLD else "pending"

        stmt = (
            pg_insert(Checkin)
            .values(
                id=body.checkin_id,
                org_id=ctx.org_id,
                user_id=ctx.user_id,
                device_id=ctx.device_id,
                site_id=site.site_id if site else None,
                ts=body.ts,
                lat=body.lat,
                lon=body.lon,
                accuracy_m=body.accuracy_m,
                inside_geofence=site.inside if site else None,
                comment=body.comment,
                ondevice_score=body.face.local_score,
                device_integrity=body.device_integrity,
                risk_score=risk_score,
                verdict=verdict,
                verdict_reasons=reasons,
            )
            .on_conflict_do_nothing(index_elements=["id"])
            .returning(Checkin.id)
        )
        inserted = (await s.execute(stmt)).scalar()

        if inserted is None:
            # Idempotent qayta-yuborish (offline-navbat retry) — mavjudini qaytaramiz
            existing = await s.get(Checkin, body.checkin_id)
            assert existing is not None
            return _to_dict(existing, duplicate=True)

        row = await s.get(Checkin, body.checkin_id)
        out = _to_dict(row)

    await get_redis().publish(
        keys.live_channel(ctx.org_id),
        json.dumps(
            {
                "type": "checkin",
                "user_id": str(ctx.user_id),
                "checkin_id": str(body.checkin_id),
                "site_id": str(site.site_id) if site else None,
                "verdict": verdict,
                "risk_score": risk_score,
                "ts": iso_utc(body.ts),
            }
        ),
    )
    return out


def _to_dict(c: Checkin, duplicate: bool = False) -> dict:
    return {
        "id": str(c.id),
        "user_id": str(c.user_id),
        "site_id": str(c.site_id) if c.site_id else None,
        "ts": c.ts,
        "lat": c.lat,
        "lon": c.lon,
        "inside_geofence": c.inside_geofence,
        "verdict": c.verdict,
        "verdict_reasons": list(c.verdict_reasons or []),
        "risk_score": c.risk_score,
        "comment": c.comment,
        "duplicate": duplicate,
    }
