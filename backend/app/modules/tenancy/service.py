"""Tenant provisioning — idempotent: mavjud slug qayta chaqirilsa xato emas,
mavjud tenant qaytadi (reja §4: provision_tenant)."""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Department, Invite, Organization, User


@dataclass
class ProvisionResult:
    org: Organization
    owner: User
    invite_token: str | None  # faqat yangi yaratilganda; keyin ko'rsatilmaydi
    invite_code: str | None
    created: bool


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _org_root_label(slug: str) -> str:
    # ltree label: [a-zA-Z0-9_] — slug'dagi chiziqchalarni almashtiramiz
    return "o_" + slug.replace("-", "_")


async def provision_tenant(
    session: AsyncSession,
    *,
    name: str,
    slug: str,
    owner_phone: str,
    owner_name: str = "Org Admin",
) -> ProvisionResult:
    existing = await session.scalar(select(Organization).where(Organization.slug == slug))
    if existing is not None:
        owner = await session.scalar(
            select(User)
            .where(User.org_id == existing.id, User.role == "org_admin")
            .order_by(User.created_at)
            .limit(1)
        )
        assert owner is not None, "org exists without an org_admin — data corruption"
        return ProvisionResult(existing, owner, None, None, created=False)

    root = _org_root_label(slug)
    org = Organization(id=uuid.uuid4(), slug=slug, name=name, ltree_root=root)
    session.add(org)
    # relationship'lar ishlatilmaydi — FK-tartibni bosqichli flush kafolatlaydi
    await session.flush()

    dept = Department(id=uuid.uuid4(), org_id=org.id, name=name, path=root)
    session.add(dept)

    await session.flush()

    owner = User(
        id=uuid.uuid4(),
        org_id=org.id,
        department_id=dept.id,
        role="org_admin",
        full_name=owner_name,
        phone=owner_phone,
    )
    session.add(owner)
    await session.flush()

    token = secrets.token_urlsafe(32)
    code = f"{secrets.randbelow(10**8):08d}"
    invite = Invite(
        id=uuid.uuid4(),
        org_id=org.id,
        employee_id=owner.id,
        token_hash=hash_token(token),
        code=code,
        expires_at=datetime.now(UTC) + timedelta(hours=get_settings().invite_ttl_hours),
    )
    session.add(invite)

    await session.flush()
    return ProvisionResult(org, owner, token, code, created=True)


async def create_employee_invite(
    session: AsyncSession, *, org_id: uuid.UUID, employee_id: uuid.UUID
) -> tuple[str, str]:
    """Xodim uchun yangi aktivatsiya-taklifi. Qaytaradi: (token, 8-belgili kod)."""
    token = secrets.token_urlsafe(32)
    code = f"{secrets.randbelow(10**8):08d}"
    session.add(
        Invite(
            org_id=org_id,
            employee_id=employee_id,
            token_hash=hash_token(token),
            code=code,
            expires_at=datetime.now(UTC) + timedelta(hours=get_settings().invite_ttl_hours),
        )
    )
    await session.flush()
    return token, code
