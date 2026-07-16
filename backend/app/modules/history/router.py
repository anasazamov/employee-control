"""Xodim-tarixi va marshrut-playback (reja §10 W3/I3).

track — soddalashtirilgan polyline (ST_Simplify), to'xtashlar, check-in pinlari,
tracking-bo'shliqlar (bo'shliq ham dalil — reja §13). timeline — obyekt-segmentlar
(site_presence'dan: "Obyekt №14: 09:15–10:40").

Har chaqiruv access_log'ga yoziladi — "kuzatuvchilarni kuzatish" (reja §12).
Mobil (o'z tarixi) va web (rahbar) bir xil endpoint'ni ishlatadi (bitta kontrakt)."""

import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, text

from app.models import AccessLog, Checkin, Site, SitePresence, User
from app.modules.rbac.deps import TenantContext, get_context, visible_user_ids

router = APIRouter(prefix="/v1/employees", tags=["history"])

GAP_SECONDS = 15 * 60  # smena payti >15 daq bo'shliq = hodisa (reja §13)


async def _assert_visible(ctx: TenantContext, user_id: uuid.UUID) -> None:
    # Mavjudlik RLS-doirasida tekshiriladi — boshqa tenant xodimi bu yerda topilmaydi
    # (org_admin/hr uchun visible=None bo'lgani uchun bu tekshiruv shart).
    async with ctx.session() as s:
        exists = await s.get(User, user_id)
    if exists is None:
        raise HTTPException(404, "xodim topilmadi")
    if str(user_id) == str(ctx.user_id):
        return
    visible = await visible_user_ids(ctx)
    if visible is not None and str(user_id) not in visible:
        raise HTTPException(404, "xodim topilmadi")


async def _log_access(s, ctx: TenantContext, subject_id: uuid.UUID, resource: str) -> None:
    s.add(
        AccessLog(
            org_id=ctx.org_id, viewer_id=ctx.user_id, subject_id=subject_id, resource=resource
        )
    )


class TrackPoint(BaseModel):
    ts: datetime
    lat: float
    lon: float


class Stop(BaseModel):
    lat: float
    lon: float
    from_ts: datetime
    to_ts: datetime
    seconds: int


class Gap(BaseModel):
    from_ts: datetime
    to_ts: datetime
    seconds: int


class CheckinPin(BaseModel):
    id: str
    ts: datetime
    lat: float
    lon: float
    verdict: str
    site_id: str | None


class TrackOut(BaseModel):
    user_id: str
    points: list[TrackPoint]
    stops: list[Stop]
    gaps: list[Gap]
    checkins: list[CheckinPin]


# ST_Simplify tolerance ~ daraja (0.00005° ≈ 5 m) — uzun marshrutni yengillashtiradi
_TRACK_SQL = text(
    """
    WITH raw AS (
        SELECT ts, ST_Y(geog::geometry) AS lat, ST_X(geog::geometry) AS lon
        FROM location_points
        WHERE user_id = :uid AND ts >= :ts_from AND ts <= :ts_to
        ORDER BY ts
    )
    SELECT ts, lat, lon FROM raw
    """
)


@router.get("/{user_id}/track", response_model=TrackOut)
async def track(
    user_id: uuid.UUID,
    ctx: TenantContext = Depends(get_context),
    ts_from: datetime = Query(...),
    ts_to: datetime = Query(...),
    stop_min_seconds: int = Query(default=300, ge=60),
    stop_radius_m: float = Query(default=50.0, ge=5),
):
    await _assert_visible(ctx, user_id)
    if ts_to <= ts_from or (ts_to - ts_from) > timedelta(days=7):
        raise HTTPException(400, "vaqt oralig'i noto'g'ri (maksimum 7 kun)")

    async with ctx.session() as s:
        rows = (
            await s.execute(
                _TRACK_SQL, {"uid": user_id, "ts_from": ts_from, "ts_to": ts_to}
            )
        ).all()
        points = [TrackPoint(ts=r.ts, lat=r.lat, lon=r.lon) for r in rows]
        stops = _detect_stops(rows, stop_min_seconds, stop_radius_m)
        gaps = _detect_gaps(rows)

        cks = (
            await s.scalars(
                select(Checkin)
                .where(
                    Checkin.user_id == user_id,
                    Checkin.ts >= ts_from,
                    Checkin.ts <= ts_to,
                )
                .order_by(Checkin.ts)
            )
        ).all()
        checkins = [
            CheckinPin(
                id=str(c.id),
                ts=c.ts,
                lat=c.lat,
                lon=c.lon,
                verdict=c.verdict,
                site_id=str(c.site_id) if c.site_id else None,
            )
            for c in cks
        ]
        await _log_access(s, ctx, user_id, "track")

    return TrackOut(
        user_id=str(user_id), points=points, stops=stops, gaps=gaps, checkins=checkins
    )


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    from math import asin, cos, radians, sin, sqrt

    r = 6371000.0
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


def _detect_stops(rows, min_seconds: int, radius_m: float) -> list[Stop]:
    stops: list[Stop] = []
    i = 0
    n = len(rows)
    while i < n:
        j = i + 1
        while j < n:
            if _haversine_m(rows[i].lat, rows[i].lon, rows[j].lat, rows[j].lon) > radius_m:
                break
            j += 1
        secs = int((rows[j - 1].ts - rows[i].ts).total_seconds())
        if j - i >= 2 and secs >= min_seconds:
            stops.append(
                Stop(
                    lat=rows[i].lat,
                    lon=rows[i].lon,
                    from_ts=rows[i].ts,
                    to_ts=rows[j - 1].ts,
                    seconds=secs,
                )
            )
            i = j
        else:
            i += 1
    return stops


def _detect_gaps(rows) -> list[Gap]:
    gaps: list[Gap] = []
    for a, b in zip(rows, rows[1:], strict=False):
        secs = int((b.ts - a.ts).total_seconds())
        if secs > GAP_SECONDS:
            gaps.append(Gap(from_ts=a.ts, to_ts=b.ts, seconds=secs))
    return gaps


class TimelineSegment(BaseModel):
    site_id: str
    site_name: str
    entered_at: datetime
    exited_at: datetime | None
    dwell_seconds: int | None


@router.get("/{user_id}/timeline", response_model=list[TimelineSegment])
async def timeline(
    user_id: uuid.UUID,
    ctx: TenantContext = Depends(get_context),
    ts_from: datetime = Query(...),
    ts_to: datetime = Query(...),
):
    """Obyekt-segmentlar: xodim qaysi obyektda qancha turgan (site_presence).
    ts_from..ts_to bilan kesishgan davrlar (ochiq davr — exited_at NULL — ham)."""
    await _assert_visible(ctx, user_id)
    async with ctx.session() as s:
        rows = (
            await s.execute(
                select(SitePresence, Site.name)
                .join(Site, Site.id == SitePresence.site_id)
                .where(
                    SitePresence.user_id == user_id,
                    SitePresence.entered_at <= ts_to,
                    (SitePresence.exited_at.is_(None))
                    | (SitePresence.exited_at >= ts_from),
                )
                .order_by(SitePresence.entered_at)
            )
        ).all()
        await _log_access(s, ctx, user_id, "timeline")
    return [
        TimelineSegment(
            site_id=str(sp.site_id),
            site_name=name,
            entered_at=sp.entered_at,
            exited_at=sp.exited_at,
            dwell_seconds=sp.dwell_seconds,
        )
        for sp, name in rows
    ]
