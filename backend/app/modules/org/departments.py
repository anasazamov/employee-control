"""Bo'limlar (departments) CRUD — org-ildizli ltree daraxt (reja §10 W6, §12 RBAC).

Yo'l ota-bo'lim ostida avtomatik quriladi; org-ildiz (ota yo'q) organizations.
ltree_root'dan olinadi. Bo'sh bo'lmagan bo'limni o'chirish taqiqlanadi (bolalar/
xodimlar yo'qolmasin)."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.models import Department, Organization, User
from app.modules.org.ltree import unique_child_path
from app.modules.rbac.deps import TenantContext, get_context, require_role

router = APIRouter(prefix="/v1/departments", tags=["departments"])


class DepartmentIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    parent_id: uuid.UUID | None = None  # None → org-ildiz ostiga


class DepartmentOut(BaseModel):
    id: str
    name: str
    path: str
    parent_id: str | None
    head_user_id: str | None
    created_at: datetime


def _out(d: Department, parent_id: str | None) -> DepartmentOut:
    return DepartmentOut(
        id=str(d.id),
        name=d.name,
        path=str(d.path),
        parent_id=parent_id,
        head_user_id=str(d.head_user_id) if d.head_user_id else None,
        created_at=d.created_at,
    )


def _parent_of(path: str) -> str | None:
    """ltree yo'ldan ota-yo'l (oxirgi label'siz)."""
    return path.rsplit(".", 1)[0] if "." in path else None


async def _parent_id(s, path: str) -> str | None:
    """Ota-bo'lim UUID'si yo'ldan hisoblanadi — create/list/patch bir xil qoida
    ishlatadi (izchillik). Ota-yo'lda bo'lim bo'lmasa (haqiqiy ildiz) → None.
    Eslatma: provision org-ildizda bo'lim yaratadi, shuning uchun API orqali
    yaratilgan "yuqori-darajali" bo'limning ota'si — o'sha ildiz-bo'lim."""
    parent_path = _parent_of(path)
    if parent_path is None:
        return None
    pid = await s.scalar(select(Department.id).where(Department.path == parent_path))
    return str(pid) if pid else None


@router.get("", response_model=list[DepartmentOut])
async def list_departments(ctx: TenantContext = Depends(get_context)):
    async with ctx.session() as s:
        depts = (await s.scalars(select(Department).order_by(Department.path))).all()
        by_path = {str(d.path): d for d in depts}
        return [
            _out(
                d,
                str(by_path[_parent_of(str(d.path))].id)
                if _parent_of(str(d.path)) in by_path
                else None,
            )
            for d in depts
        ]


@router.post("", response_model=DepartmentOut, status_code=201)
async def create_department(
    body: DepartmentIn, ctx: TenantContext = Depends(require_role("org_admin", "hr"))
):
    async with ctx.session() as s:
        if body.parent_id is not None:
            parent = await s.get(Department, body.parent_id)
            if parent is None:
                raise HTTPException(404, "ota-bo'lim topilmadi")
            parent_path = str(parent.path)
        else:
            org = await s.get(Organization, ctx.org_id)
            parent_path = org.ltree_root

        siblings = (
            await s.scalars(
                select(Department.path).where(
                    Department.path.op("~")(f"{parent_path}.*{{1}}")
                )
            )
        ).all()
        existing = {str(p).rsplit(".", 1)[-1] for p in siblings}
        new_path = unique_child_path(parent_path, body.name, existing)

        dept = Department(org_id=ctx.org_id, name=body.name, path=new_path)
        s.add(dept)
        await s.flush()
        return _out(dept, await _parent_id(s, str(dept.path)))


@router.patch("/{dept_id}", response_model=DepartmentOut)
async def patch_department(
    dept_id: uuid.UUID,
    body: DepartmentIn,
    ctx: TenantContext = Depends(require_role("org_admin", "hr")),
):
    """Nomni o'zgartirish (yo'l barqaror qoladi — bolalar-yo'llarini buzmaslik uchun)."""
    async with ctx.session() as s:
        dept = await s.get(Department, dept_id)
        if dept is None:
            raise HTTPException(404, "bo'lim topilmadi")
        dept.name = body.name
        await s.flush()
        # parent_id — UUID (create/list bilan izchil), yo'l-satr EMAS
        return _out(dept, await _parent_id(s, str(dept.path)))


@router.delete("/{dept_id}", status_code=204)
async def delete_department(
    dept_id: uuid.UUID, ctx: TenantContext = Depends(require_role("org_admin", "hr"))
):
    async with ctx.session() as s:
        dept = await s.get(Department, dept_id)
        if dept is None:
            raise HTTPException(404, "bo'lim topilmadi")
        children = await s.scalar(
            select(func.count())
            .select_from(Department)
            .where(Department.path.op("<@")(dept.path), Department.id != dept_id)
        )
        if children:
            raise HTTPException(409, "bo'sh bo'lmagan bo'lim o'chirilmaydi (ichki bo'limlar bor)")
        members = await s.scalar(
            select(func.count()).select_from(User).where(User.department_id == dept_id)
        )
        if members:
            raise HTTPException(409, "bo'limda xodimlar bor — avval ularni ko'chiring")
        await s.delete(dept)
