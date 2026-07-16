"""Auth/RBAC dependency'lari.

Har himoyalangan endpoint TenantContext oladi; DB-sessiya kerak bo'lsa
`ctx.session()` — tranzaksiyaga `SET LOCAL app.org_id` o'rnatilgan bo'ladi (RLS).
Bo'lim-doirali ko'rish (ltree subtree) resolve_visible_paths'da — hozircha
org_admin/hr → butun org, dept_head → o'z bo'limi subtree, field_employee → o'zi.
"""

import uuid
from dataclasses import dataclass

import jwt as pyjwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app.db import tenant_session
from app.models import Department, User
from app.modules.auth.security import decode_token

_bearer = HTTPBearer(auto_error=False)


@dataclass
class TenantContext:
    org_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    device_id: uuid.UUID | None

    def session(self):
        return tenant_session(self.org_id)


async def get_context(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> TenantContext:
    if creds is None:
        raise HTTPException(status_code=401, detail="token yo'q")
    try:
        payload = decode_token(creds.credentials, expected_kind="access")
    except pyjwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail="token yaroqsiz") from e
    device_id = payload.get("device_id")
    return TenantContext(
        org_id=uuid.UUID(payload["org_id"]),
        user_id=uuid.UUID(payload["sub"]),
        role=payload["role"],
        device_id=uuid.UUID(device_id) if device_id else None,
    )


def require_role(*roles: str):
    async def dep(ctx: TenantContext = Depends(get_context)) -> TenantContext:
        if ctx.role not in roles:
            raise HTTPException(status_code=403, detail="ruxsat yo'q")
        return ctx

    return dep


async def resolve_visible_paths(ctx: TenantContext) -> list[str]:
    """Chaqiruvchi ko'ra oladigan ltree-yo'llar. Repositorylar
    `WHERE departments.path <@ ANY(:paths)` qo'llaydi (org-chegara esa RLS'da)."""
    async with ctx.session() as s:
        if ctx.role in ("org_admin", "hr"):
            rows = await s.scalars(select(Department.path).where(Department.path.op("~")("*{1}")))
            return list(rows)
        me = await s.get(User, ctx.user_id)
        if me is None or me.department_id is None:
            return []
        dept = await s.get(Department, me.department_id)
        return [str(dept.path)] if dept else []
