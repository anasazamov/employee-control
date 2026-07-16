"""Org-status gate (reja §4): to'lanmagan/to'xtatilgan tenant'da yozuv-amallar
(tracking, check-in) TO'XTAYDI, o'qish ochiq qoladi (eksport uchun).

Status Redis'da 60 s keshlanadi — har so'rovda DB'ga bormaslik uchun. Suspension
platforma-konsolidan qilinganda kesh eng ko'pi bilan 60 s eskiradi (maqbul).
"""

import uuid

from fastapi import Depends, HTTPException

from app.models import Organization
from app.modules.rbac.deps import TenantContext, get_context
from app.redis import get_redis

_WRITABLE = ("active", "provisioning", "grace")
_STATUS_TTL = 60


def _status_key(org_id: uuid.UUID) -> str:
    return f"t:{org_id}:org:status"


async def org_status(org_id: uuid.UUID) -> str:
    r = get_redis()
    cached = await r.get(_status_key(org_id))
    if cached is not None:
        return cached
    # RLS'siz platforma-o'qish: status organizations'da (tenant-jadval emas)
    from app.db import plain_session

    async with plain_session() as s:
        org = await s.get(Organization, org_id)
        status = org.status if org else "purged"
    await r.set(_status_key(org_id), status, ex=_STATUS_TTL)
    return status


async def invalidate_status(org_id: uuid.UUID) -> None:
    """Platforma-konsol status o'zgartirganda chaqiriladi — keshni darhol tozalaydi."""
    await get_redis().delete(_status_key(org_id))


async def require_active_org(ctx: TenantContext = Depends(get_context)) -> TenantContext:
    """Yozuv-amallar uchun: suspended/offboarding/purged → 403."""
    status = await org_status(ctx.org_id)
    if status not in _WRITABLE:
        raise HTTPException(
            status_code=403, detail=f"tashkilot faol emas (holat: {status})"
        )
    return ctx
