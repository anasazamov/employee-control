"""Xodimlar CRUD + CSV bulk-import + aktivatsiya-invite (reja §10 W6, §14 onboarding).

Telefon TENANT ichida unikal (pudratchi boshqa org'da bo'lishi mumkin — reja §4).
CSV-import qatorli validatsiya-hisobot qaytaradi: har qator qabul/rad + sabab —
500–5000 xodimni ommaviy kiritish uchun (reja §14: "bulk-CSV")."""

import csv
import io
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.models import Department, User
from app.modules.rbac.deps import TenantContext, get_context, require_role, visible_user_ids
from app.modules.tenancy.service import create_employee_invite

router = APIRouter(prefix="/v1/users", tags=["users"])

_VALID_ROLES = ("org_admin", "hr", "dept_head", "field_employee")


class UserIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    phone: str = Field(min_length=5, max_length=20)
    role: str = Field(default="field_employee", pattern="^(org_admin|hr|dept_head|field_employee)$")
    department_id: uuid.UUID | None = None
    employee_no: str | None = None


class UserPatch(BaseModel):
    full_name: str | None = None
    role: str | None = Field(default=None, pattern="^(org_admin|hr|dept_head|field_employee)$")
    department_id: uuid.UUID | None = None
    employee_no: str | None = None
    status: str | None = Field(default=None, pattern="^(active|suspended|archived)$")


class UserOut(BaseModel):
    id: str
    full_name: str
    phone: str
    role: str
    department_id: str | None
    employee_no: str | None
    status: str
    face_enrolled_at: datetime | None
    created_at: datetime


def _out(u: User) -> UserOut:
    return UserOut(
        id=str(u.id),
        full_name=u.full_name,
        phone=u.phone,
        role=u.role,
        department_id=str(u.department_id) if u.department_id else None,
        employee_no=u.employee_no,
        status=u.status,
        face_enrolled_at=u.face_enrolled_at,
        created_at=u.created_at,
    )


async def _valid_dept(s, org_scoped_dept_id: uuid.UUID | None) -> bool:
    if org_scoped_dept_id is None:
        return True
    return (await s.get(Department, org_scoped_dept_id)) is not None


@router.post("", response_model=UserOut, status_code=201)
async def create_user(
    body: UserIn, ctx: TenantContext = Depends(require_role("org_admin", "hr"))
):
    async with ctx.session() as s:
        if not await _valid_dept(s, body.department_id):
            raise HTTPException(400, "bo'lim topilmadi")
        user = User(
            org_id=ctx.org_id,
            full_name=body.full_name,
            phone=body.phone,
            role=body.role,
            department_id=body.department_id,
            employee_no=body.employee_no,
        )
        s.add(user)
        try:
            await s.flush()
        except IntegrityError as e:
            raise HTTPException(409, "bu telefon raqami tashkilotda allaqachon mavjud") from e
        return _out(user)


@router.get("", response_model=list[UserOut])
async def list_users(
    ctx: TenantContext = Depends(get_context),
    department_id: uuid.UUID | None = None,
    status: str | None = None,
):
    visible = await visible_user_ids(ctx)
    q = select(User).order_by(User.full_name)
    if visible is not None:
        q = q.where(User.id.in_([uuid.UUID(u) for u in visible]))
    if department_id is not None:
        q = q.where(User.department_id == department_id)
    if status is not None:
        q = q.where(User.status == status)
    async with ctx.session() as s:
        return [_out(u) for u in (await s.scalars(q)).all()]


@router.patch("/{user_id}", response_model=UserOut)
async def patch_user(
    user_id: uuid.UUID,
    body: UserPatch,
    ctx: TenantContext = Depends(require_role("org_admin", "hr")),
):
    async with ctx.session() as s:
        user = await s.get(User, user_id)
        if user is None:
            raise HTTPException(404, "xodim topilmadi")
        data = body.model_dump(exclude_unset=True)
        if "department_id" in data and not await _valid_dept(s, data["department_id"]):
            raise HTTPException(400, "bo'lim topilmadi")
        for k, v in data.items():
            setattr(user, k, v)
        await s.flush()
        return _out(user)


class InviteOut(BaseModel):
    token: str  # bir marta qaytadi (QR/deep-link uchun)
    code: str  # 8-belgili qo'lda teriladigan
    user_id: str


@router.post("/{user_id}/invite", response_model=InviteOut)
async def issue_invite(
    user_id: uuid.UUID, ctx: TenantContext = Depends(require_role("org_admin", "hr"))
):
    async with ctx.session() as s:
        user = await s.get(User, user_id)
        if user is None:
            raise HTTPException(404, "xodim topilmadi")
        token, code = await create_employee_invite(s, org_id=ctx.org_id, employee_id=user_id)
        return InviteOut(token=token, code=code, user_id=str(user_id))


class ImportRowResult(BaseModel):
    row: int
    status: str  # "created" | "error"
    detail: str
    user_id: str | None = None


class ImportResult(BaseModel):
    total: int
    created: int
    errors: int
    rows: list[ImportRowResult]


@router.post("/import", response_model=ImportResult)
async def import_users(
    file: UploadFile, ctx: TenantContext = Depends(require_role("org_admin", "hr"))
):
    """CSV ustunlari: full_name, phone, [role], [department_path], [employee_no].
    department_path — mavjud bo'lim ltree-yo'li (masalan o_demo.toshkent). Har qator
    mustaqil: bittasi xato bo'lsa qolganlari baribir yaratiladi (qismli muvaffaqiyat)."""
    raw = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))
    results: list[ImportRowResult] = []
    created = 0

    async with ctx.session() as s:
        depts = (await s.scalars(select(Department))).all()
        path_to_id = {str(d.path): d.id for d in depts}
        # Oldindan-tekshiruv: mavjud + batch ichida ko'rilgan telefonlar (poyga uchun
        # savepoint backstop qoladi). Butun-tranzaksiya rollback'i o'rniga per-qator
        # savepoint — bitta xato qator qolganini bekor qilmaydi (qismli muvaffaqiyat).
        seen_phones = set((await s.scalars(select(User.phone))).all())

        for i, row in enumerate(reader, start=2):  # 1-qator sarlavha
            name = (row.get("full_name") or "").strip()
            phone = (row.get("phone") or "").strip()
            role = (row.get("role") or "field_employee").strip() or "field_employee"
            dept_path = (row.get("department_path") or "").strip()
            emp_no = (row.get("employee_no") or "").strip() or None

            if not name or not phone:
                results.append(
                    ImportRowResult(row=i, status="error", detail="full_name/phone bo'sh")
                )
                continue
            if role not in _VALID_ROLES:
                results.append(
                    ImportRowResult(row=i, status="error", detail=f"noto'g'ri rol: {role}")
                )
                continue
            if phone in seen_phones:
                results.append(
                    ImportRowResult(row=i, status="error", detail="telefon takrorlangan")
                )
                continue
            dept_id = None
            if dept_path:
                dept_id = path_to_id.get(dept_path)
                if dept_id is None:
                    results.append(
                        ImportRowResult(
                            row=i, status="error", detail=f"bo'lim topilmadi: {dept_path}"
                        )
                    )
                    continue

            user = User(
                org_id=ctx.org_id,
                full_name=name,
                phone=phone,
                role=role,
                department_id=dept_id,
                employee_no=emp_no,
            )
            try:
                async with s.begin_nested():  # savepoint: xato faqat shu qatorni orqaga qaytaradi
                    s.add(user)
                    await s.flush()
            except IntegrityError:
                # takror telefon (unikal cheklov) — savepoint bekor bo'ldi, sessiya toza
                results.append(
                    ImportRowResult(row=i, status="error", detail="telefon takrorlangan")
                )
                continue
            except DBAPIError:
                # Boshqa DB-xato (masalan 22001 — juda uzun qiymat; asyncpg buni
                # DataError'ga aniq tasniflamaydi). IntegrityError'dan KEYIN ushlanadi.
                # Savepoint faqat shu qatorni orqaga qaytaradi — qismli-muvaffaqiyat saqlanadi.
                results.append(
                    ImportRowResult(
                        row=i, status="error", detail="qiymat juda uzun yoki noto'g'ri"
                    )
                )
                continue
            seen_phones.add(phone)
            results.append(
                ImportRowResult(row=i, status="created", detail="ok", user_id=str(user.id))
            )
            created += 1

    return ImportResult(
        total=len(results),
        created=created,
        errors=len(results) - created,
        rows=results,
    )
