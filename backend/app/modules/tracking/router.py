from fastapi import APIRouter, Depends

from app.modules.rbac.deps import TenantContext, get_context, visible_user_ids
from app.modules.tracking import service
from app.modules.tracking.schemas import LocationBatchIn, LocationBatchOut

router = APIRouter(prefix="/v1/locations", tags=["tracking"])


@router.post("/batch", response_model=LocationBatchOut)
async def ingest(body: LocationBatchIn, ctx: TenantContext = Depends(get_context)):
    """Mobil ilova GPS-nuqtalarni to'plab yuboradi (≤50 nuqta/60 s tavsiya, ≤200 qabul).
    point_uuid bo'yicha idempotent — offline-bufer qayta yuborsa dublikat yaralmaydi."""
    result = await service.ingest_batch(ctx, body.points)
    return LocationBatchOut(**result)


@router.get("/last")
async def last(ctx: TenantContext = Depends(get_context)):
    """Xarita-bootstrap: oxirgi-joylashuvlar (Redis, Postgres'siz), RBAC-doiralangan."""
    visible = await visible_user_ids(ctx)
    return {"points": await service.last_locations(ctx.org_id, visible)}
