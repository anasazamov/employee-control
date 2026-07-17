"""Username/parol login (reja: username+parol auth).

credentials (auth-plane, RLS'siz) username bo'yicha topiladi → parol tekshiriladi →
org holati (suspension) + xodim holati tekshiriladi → JWT (rol users'dan). Multi-tenant:
username global-unikal, shuning uchun org login vaqtida aniqlanadi."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import plain_session, tenant_session
from app.models import Credential, User
from app.modules.auth.passwords import hash_password, verify_password
from app.modules.auth.security import issue_token
from app.modules.auth.service import AuthError
from app.modules.tenancy.status import org_status


@dataclass
class LoginResult:
    access_token: str
    refresh_token: str
    user_id: str
    org_id: str
    role: str
    full_name: str


async def login(*, username: str, password: str) -> LoginResult:
    username = username.strip().lower()
    async with plain_session() as s:
        cred = await s.scalar(select(Credential).where(Credential.username == username))
        # Vaqt-hujumga qarshi: kredensial yo'q bo'lsa ham hash-tekshiruvni "o'ynaymiz"
        stored_hash = cred.password_hash if cred else "$2b$12$" + "x" * 53
        ok = verify_password(password, stored_hash)
        if cred is None or not ok:
            raise AuthError("username yoki parol noto'g'ri")
        org_id, user_id = cred.org_id, cred.user_id

    status = await org_status(org_id)
    if status not in ("active", "provisioning", "grace"):
        raise AuthError(f"tashkilot faol emas (holat: {status})")

    async with tenant_session(org_id) as ts:
        user = await ts.get(User, user_id)
        if user is None or user.status != "active":
            raise AuthError("foydalanuvchi faol emas")
        role, full_name = user.role, user.full_name

    return LoginResult(
        access_token=issue_token(user_id=user_id, org_id=org_id, role=role, kind="access"),
        refresh_token=issue_token(user_id=user_id, org_id=org_id, role=role, kind="refresh"),
        user_id=str(user_id),
        org_id=str(org_id),
        role=role,
        full_name=full_name,
    )


async def set_credential(
    session: AsyncSession,
    *,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    username: str,
    password: str,
) -> None:
    """Xodimga username/parol o'rnatish (yaratishda yoki keyin). Mavjud bo'lsa yangilaydi.
    Chaqiruvchi tenant-sessiyada (RLS) — lekin credentials RLS'siz, shu sessiyada ishlaydi.
    Global-unikal username band bo'lsa IntegrityError → AuthError."""
    username = username.strip().lower()
    existing = await session.scalar(
        select(Credential).where(Credential.user_id == user_id)
    )
    if existing is not None:
        existing.username = username
        existing.password_hash = hash_password(password)
        existing.updated_at = datetime.now(UTC)
    else:
        session.add(
            Credential(
                username=username,
                user_id=user_id,
                org_id=org_id,
                password_hash=hash_password(password),
            )
        )
    try:
        await session.flush()
    except IntegrityError as e:
        raise AuthError(f"'{username}' username allaqachon band") from e
