"""Batch-ingestion (reja §8): idempotent hypertable-INSERT → obyekt-rezolyutsiya →
Redis last-loc/presence → org-kanalga publish (bitta pipeline'da). Jonli xarita
Postgres'ga tegmaydi — faqat Redis o'qiydi.

Eskirgan-batch himoyasi: resolve_batch tartib-qo'riqchisi (state.last_ts) kechikkan
batch holat-mashinaga kirmasligini, `advanced` flagi esa last-loc/point-hodisa
orqaga "sakramasligini" kafolatlaydi.
"""

import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.geo import point_ewkt
from app.models import Device, LocationPoint
from app.modules.rbac.deps import TenantContext
from app.modules.tracking import keys
from app.modules.tracking.presence import resolve_batch
from app.modules.tracking.schemas import LocationPointIn
from app.redis import get_redis
from app.utils import iso_utc


async def ingest_batch(ctx: TenantContext, points: list[LocationPointIn]) -> dict:
    points = sorted(points, key=lambda p: p.ts)

    async with ctx.session() as s:
        rows = [
            {
                "ts": p.ts,
                "point_uuid": p.point_uuid,
                "org_id": ctx.org_id,
                "user_id": ctx.user_id,
                "device_id": ctx.device_id,
                "geog": point_ewkt(lat=p.lat, lon=p.lon),
                "accuracy_m": p.accuracy_m,
                "speed_mps": p.speed_mps,
                "heading": p.heading,
                "battery": p.battery,
                "is_mock": p.is_mock,
                "provider": p.provider,
            }
            for p in points
        ]
        stmt = (
            pg_insert(LocationPoint)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["ts", "point_uuid"])
            .returning(LocationPoint.point_uuid)
        )
        inserted = set((await s.execute(stmt)).scalars().all())

        res = await resolve_batch(s, org_id=ctx.org_id, user_id=ctx.user_id, points=points)

        if ctx.device_id is not None:
            await s.execute(
                update(Device)
                .where(Device.id == ctx.device_id)
                .values(last_seen_at=datetime.now(UTC))
            )

    # Tranzaksiya muvaffaqiyatli — Redis-ko'rinish va publish bitta pipeline'da
    pipe = get_redis().pipeline(transaction=False)
    channel = keys.live_channel(ctx.org_id)
    latest = points[-1]

    if res.advanced:
        last = {
            "user_id": str(ctx.user_id),
            "ts": iso_utc(latest.ts),
            "lat": latest.lat,
            "lon": latest.lon,
            "accuracy_m": latest.accuracy_m,
            "battery": latest.battery,
            "is_mock": latest.is_mock,
            "site_id": res.current_site_id,
        }
        pipe.hset(keys.last_loc_hash(ctx.org_id), str(ctx.user_id), json.dumps(last))
        pipe.zadd(keys.presence_zset(ctx.org_id), {str(ctx.user_id): latest.ts.timestamp()})

    for ev in res.events:
        pipe.publish(
            channel,
            json.dumps(
                {
                    "type": ev.type,
                    "user_id": str(ev.user_id),
                    "site_id": ev.site_id,
                    "ts": iso_utc(ev.ts),
                    "dwell_seconds": ev.dwell_seconds,
                }
            ),
        )
    if res.advanced:
        pipe.publish(channel, json.dumps({"type": "point", **last}))
    await pipe.execute()

    return {
        "accepted": len(inserted),
        "duplicates": len(points) - len(inserted),
        "current_site_id": res.current_site_id,
    }


async def last_locations(org_id: uuid.UUID, visible: set[str] | None) -> list[dict]:
    """Redis'dagi oxirgi-joylashuvlar; visible=None — org bo'yicha hammasi (RBAC yuqorida)."""
    raw = await get_redis().hgetall(keys.last_loc_hash(org_id))
    out = []
    for user_id, payload in raw.items():
        if visible is not None and user_id not in visible:
            continue
        out.append(json.loads(payload))
    return out
