import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from app.models import AuditLog, Checkin
from app.modules.checkins import service
from app.modules.checkins.schemas import CheckinIn, CheckinOut, CommentIn, ReviewIn
from app.modules.rbac.deps import TenantContext, get_context, require_role, visible_user_ids
from app.modules.tenancy.status import require_active_org

router = APIRouter(prefix="/v1/checkins", tags=["checkins"])

_MANAGER_ROLES = ("org_admin", "hr", "dept_head")


def _audit(s, ctx: TenantContext, action: str, object_id: uuid.UUID, detail: dict):
    s.add(
        AuditLog(
            org_id=ctx.org_id,
            actor_id=ctx.user_id,
            action=action,
            object_type="checkin",
            object_id=object_id,
            detail=detail,
        )
    )


@router.post("", response_model=CheckinOut)
async def create(body: CheckinIn, ctx: TenantContext = Depends(require_active_org)):
    try:
        return await service.create_checkin(ctx, body)
    except service.SignatureError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("", response_model=list[CheckinOut])
async def list_checkins(
    ctx: TenantContext = Depends(get_context),
    user_id: uuid.UUID | None = None,
    site_id: uuid.UUID | None = None,
    verdict: str | None = Query(default=None, pattern="^(pending|verified|flagged|rejected)$"),
    ts_from: datetime | None = None,
    ts_to: datetime | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    visible = await visible_user_ids(ctx)
    q = select(Checkin).order_by(Checkin.ts.desc()).limit(limit).offset(offset)
    if user_id is not None:
        if visible is not None and str(user_id) not in visible:
            return []
        q = q.where(Checkin.user_id == user_id)
    elif visible is not None:
        q = q.where(Checkin.user_id.in_([uuid.UUID(u) for u in visible]))
    if site_id is not None:
        q = q.where(Checkin.site_id == site_id)
    if verdict is not None:
        q = q.where(Checkin.verdict == verdict)
    if ts_from is not None:
        q = q.where(Checkin.ts >= ts_from)
    if ts_to is not None:
        q = q.where(Checkin.ts <= ts_to)
    async with ctx.session() as s:
        rows = (await s.scalars(q)).all()
        return [service._to_dict(c) for c in rows]


@router.get("/review-queue", response_model=list[CheckinOut])
async def review_queue(
    ctx: TenantContext = Depends(require_role(*_MANAGER_ROLES)),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    """W4 review-navbat: bayroqlangan check-in'lar (keyinroq: offline/past-ball ham)."""
    visible = await visible_user_ids(ctx)
    q = (
        select(Checkin)
        .where(Checkin.verdict == "flagged")
        .order_by(Checkin.ts.desc())
        .limit(limit)
        .offset(offset)
    )
    if visible is not None:
        q = q.where(Checkin.user_id.in_([uuid.UUID(u) for u in visible]))
    async with ctx.session() as s:
        rows = (await s.scalars(q)).all()
        return [service._to_dict(c) for c in rows]


async def _load_scoped(s, ctx: TenantContext, checkin_id: uuid.UUID) -> Checkin:
    c = await s.get(Checkin, checkin_id)
    if c is None:
        raise HTTPException(404, "check-in topilmadi")
    if str(c.user_id) != str(ctx.user_id):
        visible = await visible_user_ids(ctx)
        if visible is not None and str(c.user_id) not in visible:
            raise HTTPException(404, "check-in topilmadi")
    return c


@router.get("/{checkin_id}", response_model=CheckinOut)
async def get_checkin(checkin_id: uuid.UUID, ctx: TenantContext = Depends(get_context)):
    async with ctx.session() as s:
        return service._to_dict(await _load_scoped(s, ctx, checkin_id))


@router.post("/{checkin_id}/comment", response_model=CheckinOut)
async def add_comment(
    checkin_id: uuid.UUID, body: CommentIn, ctx: TenantContext = Depends(get_context)
):
    """Izoh append-only: imzolangan yozuv o'zgarmaydi, keyingi izohlar qo'shiladi
    va har biri audit_log'da (reja §9)."""
    async with ctx.session() as s:
        c = await _load_scoped(s, ctx, checkin_id)
        c.comment = (c.comment + "\n" if c.comment else "") + body.text
        _audit(s, ctx, "checkin_comment_appended", c.id, {"text": body.text})
        await s.flush()
        return service._to_dict(c)


@router.post("/{checkin_id}/review", response_model=CheckinOut)
async def review(
    checkin_id: uuid.UUID,
    body: ReviewIn,
    ctx: TenantContext = Depends(require_role(*_MANAGER_ROLES)),
):
    """Har qaror sabab bilan va audit_log'da (reja W4).
    TODO(v2): reviewer-javobgarligi — tasdiqlangan bayroqlilarning 5% yuqori
    daraja qayta ko'radi (reja §13)."""
    async with ctx.session() as s:
        c = await _load_scoped(s, ctx, checkin_id)
        c.verdict = "verified" if body.action == "approve" else "rejected"
        c.reviewed_by = ctx.user_id
        c.reviewed_at = datetime.now(UTC)
        _audit(
            s, ctx, "checkin_reviewed", c.id, {"action": body.action, "reason": body.reason}
        )
        await s.flush()
        return service._to_dict(c)
