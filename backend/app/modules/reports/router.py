"""Anti-fraud analitika (reja §13 v3, W7) — xodim-integrity leaderboard.

Har inspektor bo'yicha davr-metrikalari va kompozit anomaliya-ball. Tizim faqat
KO'RSATADI; qaror odam zimmasida (reja §12: "Humans investigate; the system only
points"). Rahbar-doiraga (visible_user_ids) filtrlangan; ko'rish access_log'da.

Metrikalar (mavjud ma'lumotdan):
- flagged_ratio — bayroqlangan/jami check-in;
- avg_risk — o'rtacha risk-ball;
- short_dwell_ratio — min-dwell'dan qisqa tashriflar ulushi (haydab-o'tish signali);
- assignment_miss_ratio — o'tkazib yuborilgan topshiriqlar ulushi.
Kompozit anomaliya-ball = shu signallarning vaznli yig'indisi (0–100).
TODO(v2): tracking-gap-ratio (location_points skani), juftlik-pattern, geofence-chet.
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import Float, case, cast, func, select

from app.models import AccessLog, Assignment, Checkin, Site, SitePresence, User
from app.modules.rbac.deps import TenantContext, require_role, visible_user_ids

router = APIRouter(prefix="/v1/reports", tags=["reports"])
_MANAGER = ("org_admin", "hr", "dept_head")

# Kompozit anomaliya-ball vaznlari (jami 100)
W_FLAGGED = 40
W_RISK = 20  # avg_risk/100 * W_RISK
W_SHORT_DWELL = 25
W_MISS = 15


class EmployeeIntegrity(BaseModel):
    user_id: str
    full_name: str
    checkins: int
    flagged: int
    flagged_ratio: float
    avg_risk: float
    visits: int
    short_dwell: int
    short_dwell_ratio: float
    assignments_total: int
    assignments_missed: int
    assignment_miss_ratio: float
    anomaly_score: int


class IntegrityReport(BaseModel):
    ts_from: datetime
    ts_to: datetime
    rows: list[EmployeeIntegrity]


@router.get("/employee-integrity", response_model=IntegrityReport)
async def employee_integrity(
    ctx: TenantContext = Depends(require_role(*_MANAGER)),
    ts_from: datetime | None = None,
    ts_to: datetime | None = None,
    limit: int = Query(default=100, le=500),
):
    now = datetime.now(UTC)
    ts_from = ts_from or (now - timedelta(days=30))
    ts_to = ts_to or now
    visible = await visible_user_ids(ctx)

    async with ctx.session() as s:
        # Check-in agregatlari (bayroqli-nisbat, o'rtacha risk)
        ck_q = (
            select(
                Checkin.user_id,
                func.count().label("cnt"),
                func.sum(case((Checkin.verdict == "flagged", 1), else_=0)).label("flagged"),
                func.coalesce(func.avg(cast(Checkin.risk_score, Float)), 0.0).label("avg_risk"),
            )
            .where(Checkin.ts >= ts_from, Checkin.ts <= ts_to)
            .group_by(Checkin.user_id)
        )
        if visible is not None:
            ck_q = ck_q.where(Checkin.user_id.in_([uuid.UUID(u) for u in visible]))
        ck = {r.user_id: r for r in (await s.execute(ck_q)).all()}

        # Tashrif + min-dwell buzilishi (yopiq davrlar; site.min_dwell bilan solishtirish)
        sp_q = (
            select(
                SitePresence.user_id,
                func.count().label("visits"),
                func.sum(
                    case(
                        (
                            SitePresence.dwell_seconds < Site.min_dwell_minutes * 60,
                            1,
                        ),
                        else_=0,
                    )
                ).label("short_dwell"),
            )
            .join(Site, Site.id == SitePresence.site_id)
            .where(
                SitePresence.exited_at.isnot(None),
                SitePresence.entered_at >= ts_from,
                SitePresence.entered_at <= ts_to,
            )
            .group_by(SitePresence.user_id)
        )
        if visible is not None:
            sp_q = sp_q.where(SitePresence.user_id.in_([uuid.UUID(u) for u in visible]))
        sp = {r.user_id: r for r in (await s.execute(sp_q)).all()}

        # Topshiriq bajarilishi
        as_q = (
            select(
                Assignment.employee_id,
                func.count().label("total"),
                func.sum(case((Assignment.status == "missed", 1), else_=0)).label("missed"),
            )
            .where(Assignment.created_at >= ts_from, Assignment.created_at <= ts_to)
            .group_by(Assignment.employee_id)
        )
        if visible is not None:
            as_q = as_q.where(Assignment.employee_id.in_([uuid.UUID(u) for u in visible]))
        asg = {r.employee_id: r for r in (await s.execute(as_q)).all()}

        # Faol xodimlar (metrikalari bo'lganlar birlashmasi)
        uids = set(ck) | set(sp) | set(asg)
        names = dict(
            (
                await s.execute(select(User.id, User.full_name).where(User.id.in_(uids)))
            ).all()
        ) if uids else {}

        s.add(
            AccessLog(
                org_id=ctx.org_id,
                viewer_id=ctx.user_id,
                subject_id=None,
                resource="report:employee-integrity",
            )
        )

    rows: list[EmployeeIntegrity] = []
    for uid in uids:
        c = ck.get(uid)
        p = sp.get(uid)
        a = asg.get(uid)
        cnt = c.cnt if c else 0
        flagged = int(c.flagged) if c else 0
        avg_risk = float(c.avg_risk) if c else 0.0
        visits = p.visits if p else 0
        short = int(p.short_dwell) if p else 0
        a_total = a.total if a else 0
        a_missed = int(a.missed) if a else 0

        flagged_ratio = flagged / cnt if cnt else 0.0
        short_ratio = short / visits if visits else 0.0
        miss_ratio = a_missed / a_total if a_total else 0.0

        anomaly = round(
            W_FLAGGED * flagged_ratio
            + W_RISK * (avg_risk / 100.0)
            + W_SHORT_DWELL * short_ratio
            + W_MISS * miss_ratio
        )
        rows.append(
            EmployeeIntegrity(
                user_id=str(uid),
                full_name=names.get(uid, "?"),
                checkins=cnt,
                flagged=flagged,
                flagged_ratio=round(flagged_ratio, 3),
                avg_risk=round(avg_risk, 1),
                visits=visits,
                short_dwell=short,
                short_dwell_ratio=round(short_ratio, 3),
                assignments_total=a_total,
                assignments_missed=a_missed,
                assignment_miss_ratio=round(miss_ratio, 3),
                anomaly_score=min(100, anomaly),
            )
        )

    # Eng shubhali tepada (leaderboard)
    rows.sort(key=lambda r: r.anomaly_score, reverse=True)
    return IntegrityReport(ts_from=ts_from, ts_to=ts_to, rows=rows[:limit])
