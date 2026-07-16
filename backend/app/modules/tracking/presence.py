"""Obyekt-rezolyutsiya ("kim qaysi obyektda") — reja §8.

Gisterezis (geofence chetidagi GPS-drift enter/exit'ni "chaqnatmasligi" uchun):
  ENTER — 2 ketma-ket ichki fix YOKI aniqligi radius/2 dan yaxshi 1 fix;
  EXIT  — joriy obyektdan tashqarida >= 120 s; chiqish vaqti = birinchi tashqi
          fix (out_since) — dwell konservativ hisoblanadi (anti-fraud foydasiga).

Holat foydalanuvchi boshiga BITTA Redis-kalitda (JSON) — batch boshida bir marta
o'qiladi, oxirida bir marta yoziladi (nuqta boshiga round-trip YO'Q).
Tartib-qo'riqchi: state.last_ts dan eski nuqtalar holat-mashinaga kirmaydi
(DB'ga baribir yoziladi — dalil), kechikkan/takror batch'lar gisterezisni buzmaydi.

Eslatma: Redis-holat DB-tranzaksiya bilan atomik emas; rollback'da keyingi batch
o'zini tuzatadi. Bir foydalanuvchining PARALLEL batch'lari holat ustida poyga
qilishi mumkin — mobil mijoz ketma-ket yuboradi; TODO(v2): per-user lock/outbox.
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SitePresence
from app.modules.tracking import keys
from app.redis import get_redis
from app.utils import iso_utc

ENTER_CONSECUTIVE = 2
EXIT_SECONDS = 120  # TODO(tenant-config): organizations.settings dan o'qish


@dataclass
class PresenceEvent:
    type: str  # "site_enter" | "site_exit"
    user_id: uuid.UUID
    site_id: str
    ts: datetime
    dwell_seconds: int | None = None


@dataclass
class _State:
    cur_site: str | None = None
    row_id: str | None = None
    out_since: str | None = None  # iso
    cand_site: str | None = None
    in_count: int = 0
    last_ts: str | None = None  # iso — holat-mashina ko'rgan eng yangi nuqta


@dataclass
class BatchResult:
    events: list[PresenceEvent] = field(default_factory=list)
    current_site_id: str | None = None
    # Batch holat-mashinaga yangi (eng so'nggi) nuqta kiritdimi — last-loc'ni
    # eskirgan batch qayta yozmasligi uchun
    advanced: bool = False


_FIND_SITE = text(
    """
    SELECT id, radius_m FROM sites
    WHERE status = 'active' AND (
        ST_DWithin(center, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, radius_m)
        OR (geom IS NOT NULL
            AND ST_Contains(geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)))
    )
    ORDER BY ST_Distance(center, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography)
    LIMIT 1
    """
)


async def _load_state(org_id: uuid.UUID, user_id: uuid.UUID) -> _State:
    raw = await get_redis().get(keys.sp_state_hash(org_id, user_id))
    if not raw:
        return _State()
    return _State(**json.loads(raw))


async def _save_state(org_id: uuid.UUID, user_id: uuid.UUID, st: _State) -> None:
    await get_redis().set(
        keys.sp_state_hash(org_id, user_id),
        json.dumps(
            {
                "cur_site": st.cur_site,
                "row_id": st.row_id,
                "out_since": st.out_since,
                "cand_site": st.cand_site,
                "in_count": st.in_count,
                "last_ts": st.last_ts,
            }
        ),
    )


async def resolve_batch(
    session: AsyncSession,
    *,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    points: list,  # LocationPointIn, ts bo'yicha saralangan
) -> BatchResult:
    """Batch'ni gisterezis-mashinadan o'tkazadi. Holat: 1 GET boshida, 1 SET oxirida.
    session — tenant-sessiya (RLS org'ni o'zi filtrlaydi)."""
    st = await _load_state(org_id, user_id)
    res = BatchResult()
    # In-batch geo-memo: turg'un xodim deyarli bir xil fix'lar yuboradi —
    # ~11 m aniqlikda yumaloqlash bitta PostGIS-so'rovni qayta ishlatadi
    memo: dict[tuple[float, float], tuple[str, int] | None] = {}

    for p in points:
        if st.last_ts and p.ts <= datetime.fromisoformat(st.last_ts):
            continue  # tartib-qo'riqchi: eski/takror nuqta holatni buzmaydi
        st.last_ts = iso_utc(p.ts)
        res.advanced = True

        mkey = (round(p.lat, 4), round(p.lon, 4))
        if mkey in memo:
            found = memo[mkey]
        else:
            row = (await session.execute(_FIND_SITE, {"lat": p.lat, "lon": p.lon})).first()
            found = (str(row.id), row.radius_m) if row else None
            memo[mkey] = found
        found_id = found[0] if found else None

        if st.cur_site:
            if found_id == st.cur_site:
                st.out_since = None
            elif st.out_since is None:
                st.out_since = iso_utc(p.ts)
            elif (p.ts - datetime.fromisoformat(st.out_since)).total_seconds() >= EXIT_SECONDS:
                exited_at = datetime.fromisoformat(st.out_since)
                sp = await session.get(SitePresence, uuid.UUID(st.row_id))
                if sp is not None and sp.exited_at is None:
                    sp.exited_at = exited_at
                    sp.dwell_seconds = max(0, int((exited_at - sp.entered_at).total_seconds()))
                    await session.flush()
                    res.events.append(
                        PresenceEvent(
                            type="site_exit",
                            user_id=user_id,
                            site_id=st.cur_site,
                            ts=exited_at,
                            dwell_seconds=sp.dwell_seconds,
                        )
                    )
                st.cur_site = st.row_id = st.out_since = None
                # yangi obyektga kirish quyida shu nuqta bilan tekshiriladi

        if st.cur_site is None and found is not None:
            found_id, radius_m = found
            instant = p.accuracy_m is not None and p.accuracy_m < radius_m / 2
            if not instant:
                st.in_count = st.in_count + 1 if st.cand_site == found_id else 1
                st.cand_site = found_id
                if st.in_count < ENTER_CONSECUTIVE:
                    continue
            sp = SitePresence(
                org_id=org_id, user_id=user_id, site_id=uuid.UUID(found_id), entered_at=p.ts
            )
            session.add(sp)
            await session.flush()
            st.cur_site, st.row_id = found_id, str(sp.id)
            st.cand_site, st.in_count, st.out_since = None, 0, None
            res.events.append(
                PresenceEvent(type="site_enter", user_id=user_id, site_id=found_id, ts=p.ts)
            )
        elif st.cur_site is None:
            st.cand_site, st.in_count = None, 0

    res.current_site_id = st.cur_site
    await _save_state(org_id, user_id, st)
    return res
