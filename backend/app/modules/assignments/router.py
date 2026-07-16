"""Topshiriqlar (assignments) — "inspektor X obyekt Y'ni Z sanagacha tekshirsin"
(reja §5, §10). Check-in yaratilganda mos ochiq topshiriq avtomatik 'completed'
bo'ladi (checkins.service ichida). Compliance-summary tashrif-bajarilish %'ini beradi.

TODO(v2): reveal_at (kech-ochish) + rotatsiya (reja §13); dwell-shartli complete."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.models import Assignment, Site, User
from app.modules.rbac.deps import TenantContext, get_context, require_role, visible_user_ids

router = APIRouter(tags=["assignments"])
_MANAGER = ("org_admin", "hr", "dept_head")
_STATUSES = ("pending", "in_progress", "completed", "missed", "cancelled")
_STATUS_PATTERN = "^(pending|in_progress|completed|missed|cancelled)$"


class AssignmentIn(BaseModel):
    site_id: uuid.UUID
    employee_id: uuid.UUID
    due_from: datetime | None = None
    due_to: datetime | None = None
    min_dwell_minutes: int | None = Field(default=None, ge=0, le=480)


class AssignmentPatch(BaseModel):
    status: str | None = Field(default=None, pattern=_STATUS_PATTERN)
    due_from: datetime | None = None
    due_to: datetime | None = None


class AssignmentOut(BaseModel):
    id: str
    site_id: str
    site_name: str | None
    employee_id: str
    status: str
    due_from: datetime | None
    due_to: datetime | None
    created_at: datetime


def _out(a: Assignment, site_name: str | None) -> AssignmentOut:
    return AssignmentOut(
        id=str(a.id),
        site_id=str(a.site_id),
        site_name=site_name,
        employee_id=str(a.employee_id),
        status=a.status,
        due_from=a.due_from,
        due_to=a.due_to,
        created_at=a.created_at,
    )


@router.post("/v1/assignments", response_model=AssignmentOut, status_code=201)
async def create_assignment(
    body: AssignmentIn, ctx: TenantContext = Depends(require_role(*_MANAGER))
):
    async with ctx.session() as s:
        site = await s.get(Site, body.site_id)
        if site is None:
            raise HTTPException(400, "obyekt topilmadi")
        emp = await s.get(User, body.employee_id)
        if emp is None:
            raise HTTPException(400, "xodim topilmadi")
        a = Assignment(
            org_id=ctx.org_id,
            site_id=body.site_id,
            employee_id=body.employee_id,
            assigned_by=ctx.user_id,
            due_from=body.due_from,
            due_to=body.due_to,
            min_dwell_minutes=body.min_dwell_minutes,
        )
        s.add(a)
        await s.flush()
        return _out(a, site.name)


async def _scoped_query(ctx: TenantContext, base):
    """Faqat ko'rinadigan xodimlarning topshiriqlari (RBAC-doira)."""
    visible = await visible_user_ids(ctx)
    if visible is not None:
        base = base.where(Assignment.employee_id.in_([uuid.UUID(u) for u in visible]))
    return base


@router.get("/v1/assignments", response_model=list[AssignmentOut])
async def list_assignments(
    ctx: TenantContext = Depends(get_context),
    employee_id: uuid.UUID | None = None,
    site_id: uuid.UUID | None = None,
    status: str | None = Query(default=None, pattern=_STATUS_PATTERN),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
):
    q = (
        select(Assignment, Site.name)
        .join(Site, Site.id == Assignment.site_id)
        .order_by(Assignment.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    q = await _scoped_query(ctx, q)
    if employee_id is not None:
        q = q.where(Assignment.employee_id == employee_id)
    if site_id is not None:
        q = q.where(Assignment.site_id == site_id)
    if status is not None:
        q = q.where(Assignment.status == status)
    async with ctx.session() as s:
        rows = (await s.execute(q)).all()
        return [_out(a, name) for a, name in rows]


@router.get("/v1/me/assignments", response_model=list[AssignmentOut])
async def my_assignments(
    ctx: TenantContext = Depends(get_context),
    status: str | None = Query(default=None, pattern=_STATUS_PATTERN),
):
    """Mobil "topshiriqlar" ekrani — xodimning o'z topshiriqlari."""
    q = (
        select(Assignment, Site.name)
        .join(Site, Site.id == Assignment.site_id)
        .where(Assignment.employee_id == ctx.user_id)
        .order_by(Assignment.due_to.nulls_last(), Assignment.created_at.desc())
    )
    if status is not None:
        q = q.where(Assignment.status == status)
    async with ctx.session() as s:
        rows = (await s.execute(q)).all()
        return [_out(a, name) for a, name in rows]


@router.patch("/v1/assignments/{assignment_id}", response_model=AssignmentOut)
async def patch_assignment(
    assignment_id: uuid.UUID,
    body: AssignmentPatch,
    ctx: TenantContext = Depends(require_role(*_MANAGER)),
):
    async with ctx.session() as s:
        a = await s.get(Assignment, assignment_id)
        if a is None:
            raise HTTPException(404, "topshiriq topilmadi")
        for k, v in body.model_dump(exclude_unset=True).items():
            setattr(a, k, v)
        await s.flush()
        site = await s.get(Site, a.site_id)
        return _out(a, site.name if site else None)


class ComplianceRow(BaseModel):
    status: str
    count: int


class ComplianceSummary(BaseModel):
    total: int
    completed: int
    completion_rate: float
    by_status: list[ComplianceRow]


@router.get("/v1/assignments/summary", response_model=ComplianceSummary)
async def compliance_summary(
    ctx: TenantContext = Depends(require_role(*_MANAGER)),
    ts_from: datetime | None = None,
    ts_to: datetime | None = None,
):
    """Tashrif-bajarilish %: davr bo'yicha topshiriqlar holati (reja W7)."""
    q = select(Assignment.status, func.count()).group_by(Assignment.status)
    q = await _scoped_query(ctx, q)
    if ts_from is not None:
        q = q.where(Assignment.created_at >= ts_from)
    if ts_to is not None:
        q = q.where(Assignment.created_at <= ts_to)
    async with ctx.session() as s:
        rows = (await s.execute(q)).all()
    by_status = {status: count for status, count in rows}
    total = sum(by_status.values())
    completed = by_status.get("completed", 0)
    return ComplianceSummary(
        total=total,
        completed=completed,
        completion_rate=round(completed / total, 4) if total else 0.0,
        by_status=[ComplianceRow(status=s, count=c) for s, c in by_status.items()],
    )
