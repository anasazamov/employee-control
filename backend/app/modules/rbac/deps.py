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


def context_from_token(token: str) -> TenantContext:
    """Access-token → TenantContext — HTTP (get_context) va WS (/v1/live) uchun
    YAGONA yo'l; claim-to'plami o'zgarsa bitta joy o'zgaradi.
    PyJWTError'ni chaqiruvchi o'zi 401/4401 ga aylantiradi."""
    payload = decode_token(token, expected_kind="access")
    device_id = payload.get("device_id")
    return TenantContext(
        org_id=uuid.UUID(payload["org_id"]),
        user_id=uuid.UUID(payload["sub"]),
        role=payload["role"],
        device_id=uuid.UUID(device_id) if device_id else None,
    )


async def get_context(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> TenantContext:
    if creds is None:
        raise HTTPException(status_code=401, detail="token yo'q")
    try:
        return context_from_token(creds.credentials)
    except pyjwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail="token yaroqsiz") from e


def require_role(*roles: str):
    async def dep(ctx: TenantContext = Depends(get_context)) -> TenantContext:
        if ctx.role not in roles:
            raise HTTPException(status_code=403, detail="ruxsat yo'q")
        return ctx

    return dep


async def visible_user_ids(ctx: TenantContext) -> set[str] | None:
    """Chaqiruvchi ko'ra oladigan xodim-id'lar (str). None = org bo'yicha hammasi.
    org_admin/hr → hammasi; dept_head → o'z bo'limi subtree'si; field_employee → o'zi.
    Org-chegara baribir RLS/kanal-prefiksda — bu faqat ichki doiralash."""
    if ctx.role in ("org_admin", "hr"):
        return None
    self_only = {str(ctx.user_id)}
    if ctx.role == "field_employee":
        return self_only
    async with ctx.session() as s:
        me = await s.get(User, ctx.user_id)
        dept = await s.get(Department, me.department_id) if me and me.department_id else None
        if dept is None:
            return self_only
        rows = await s.execute(
            select(User.id)
            .join(Department, Department.id == User.department_id)
            .where(Department.path.op("<@")(dept.path))
        )
        return self_only | {str(r[0]) for r in rows}


