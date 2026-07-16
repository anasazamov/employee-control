"""Smena (roster) API — tracking faqat smena ichida yuradi (reja §8):
mobil ilova GET /v1/me/shift bilan joriy/keyingi smenani oladi va lokatsiya-
servisni shunga qarab yoqadi/o'chiradi. Smena tashqarisida NOL lokatsiya."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select

from app.models import Shift, User
from app.modules.rbac.deps import TenantContext, get_context, require_role, visible_user_ids

router = APIRouter(tags=["shifts"])


class ShiftIn(BaseModel):
    user_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime

    @model_validator(mode="after")
    def _order(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at starts_at'dan keyin bo'lishi kerak")
        return self


class ShiftBulkIn(BaseModel):
    shifts: list[ShiftIn] = Field(min_length=1, max_length=500)


class ShiftOut(BaseModel):
    id: str
    user_id: str
    starts_at: datetime
    ends_at: datetime


def _out(sh: Shift) -> ShiftOut:
    return ShiftOut(
        id=str(sh.id), user_id=str(sh.user_id), starts_at=sh.starts_at, ends_at=sh.ends_at
    )


@router.post("/v1/shifts", response_model=list[ShiftOut], status_code=201)
async def create_shifts(
    body: ShiftBulkIn, ctx: TenantContext = Depends(require_role("org_admin", "hr"))
):
    async with ctx.session() as s:
        user_ids = {sh.user_id for sh in body.shifts}
        found = set(
            (await s.scalars(select(User.id).where(User.id.in_(user_ids)))).all()
        )
        missing = user_ids - found
        if missing:
            raise HTTPException(400, f"xodim topilmadi: {', '.join(str(m) for m in missing)}")
        rows = [
            Shift(
                org_id=ctx.org_id,
                user_id=sh.user_id,
                starts_at=sh.starts_at,
                ends_at=sh.ends_at,
            )
            for sh in body.shifts
        ]
        s.add_all(rows)
        await s.flush()
        return [_out(sh) for sh in rows]


@router.get("/v1/shifts", response_model=list[ShiftOut])
async def list_shifts(
    ctx: TenantContext = Depends(get_context),
    user_id: uuid.UUID | None = None,
    ts_from: datetime | None = None,
    ts_to: datetime | None = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
):
    visible = await visible_user_ids(ctx)
    q = select(Shift).order_by(Shift.starts_at).limit(limit).offset(offset)
    if user_id is not None:
        if visible is not None and str(user_id) not in visible:
            return []
        q = q.where(Shift.user_id == user_id)
    elif visible is not None:
        q = q.where(Shift.user_id.in_([uuid.UUID(u) for u in visible]))
    if ts_from is not None:
        q = q.where(Shift.ends_at >= ts_from)
    if ts_to is not None:
        q = q.where(Shift.starts_at <= ts_to)
    async with ctx.session() as s:
        return [_out(sh) for sh in (await s.scalars(q)).all()]


@router.get("/v1/me/shift")
async def my_shift(ctx: TenantContext = Depends(get_context)):
    """Mobil tracking-gate: joriy smena (bo'lsa) va keyingi smena."""
    now = datetime.now(UTC)
    async with ctx.session() as s:
        current = await s.scalar(
            select(Shift)
            .where(Shift.user_id == ctx.user_id, Shift.starts_at <= now, Shift.ends_at > now)
            .order_by(Shift.starts_at)
            .limit(1)
        )
        upcoming = await s.scalar(
            select(Shift)
            .where(Shift.user_id == ctx.user_id, Shift.starts_at > now)
            .order_by(Shift.starts_at)
            .limit(1)
        )
    return {
        "current": _out(current).model_dump() if current else None,
        "next": _out(upcoming).model_dump() if upcoming else None,
    }
