"""Invite-asosli aktivatsiya (reja §7):
org yuzdan OLDIN invite orqali aniqlanadi → SMS OTP (dev'da logga) → qurilma-bog'lash → JWT.

Yuz-tekshiruv (1:1/1:N) keyingi sprintda `face` moduliga qo'shiladi — bu oqim
o'shanda ham o'zgarmaydi: yuz qadami OTP'dan oldin kiritiladi.
"""

import hashlib
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import plain_session, tenant_session
from app.models import Device, Invite, Organization, OtpCode, User
from app.modules.auth.security import issue_token
from app.modules.tenancy.service import hash_token

logger = logging.getLogger(__name__)


class AuthError(Exception):
    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


@dataclass
class ResolvedInvite:
    org_id: uuid.UUID
    org_name: str
    org_settings: dict
    employee_id: uuid.UUID | None
    masked_phone: str | None


def _mask_phone(phone: str) -> str:
    return phone[:-7] + "*****" + phone[-2:] if len(phone) >= 9 else "***"


async def _load_valid_invite(session: AsyncSession, token: str) -> Invite:
    invite = await session.scalar(
        select(Invite).where(Invite.token_hash == hash_token(token))
    )
    if invite is None:
        raise AuthError("invite topilmadi")
    if invite.used_at is not None:
        raise AuthError("invite allaqachon ishlatilgan")
    expires = invite.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if expires < datetime.now(UTC):
        raise AuthError("invite muddati o'tgan")
    return invite


async def resolve_invite(token: str) -> ResolvedInvite:
    async with plain_session() as session:
        invite = await _load_valid_invite(session, token)
        org = await session.get(Organization, invite.org_id)
        assert org is not None
        if org.status not in ("active", "provisioning"):
            raise AuthError("tashkilot faol emas")
        masked = None
        if invite.employee_id is not None:
            async with tenant_session(invite.org_id) as ts:
                user = await ts.get(User, invite.employee_id)
                if user is not None:
                    masked = _mask_phone(user.phone)
        return ResolvedInvite(
            org_id=org.id,
            org_name=org.name,
            org_settings=org.settings,
            employee_id=invite.employee_id,
            masked_phone=masked,
        )


async def request_otp(*, invite_token: str, purpose: str = "activation") -> str | None:
    """OTP yaratadi. Dev'da kodni qaytaradi (SMS integratsiyasi — Eskiz — keyinroq);
    prod'da None qaytadi va kod faqat SMS orqali boradi."""
    resolved = await resolve_invite(invite_token)
    if resolved.employee_id is None:
        raise AuthError("org-wide invite uchun avval xodim tanlanishi kerak (1:N — keyingi sprint)")

    async with tenant_session(resolved.org_id) as ts:
        user = await ts.get(User, resolved.employee_id)
        if user is None:
            raise AuthError("xodim topilmadi")
        phone = user.phone

    code = f"{secrets.randbelow(10**6):06d}"
    async with plain_session() as session:
        session.add(
            OtpCode(
                phone=phone,
                code_hash=hashlib.sha256(code.encode()).hexdigest(),
                purpose=purpose,
                expires_at=datetime.now(UTC)
                + timedelta(seconds=get_settings().otp_ttl_seconds),
            )
        )

    # TODO(eskiz): SMS-yuborish provayder-adapteri (Eskiz asosiy, Play Mobile failover)
    logger.info("OTP for %s: %s", _mask_phone(phone), code)
    return code if get_settings().debug else None


async def activate(
    *,
    invite_token: str,
    otp_code: str,
    device_platform: str,
    device_fingerprint: str,
    device_model: str | None = None,
) -> dict:
    """Invite + OTP → qurilma-bog'lash → JWT juftligi.
    1 faol qurilma/(org, xodim): yangi bog'lash eskilarini bekor qiladi (reja §7.5)."""
    resolved = await resolve_invite(invite_token)
    if resolved.employee_id is None:
        raise AuthError("org-wide invite hali qo'llab-quvvatlanmaydi")

    async with tenant_session(resolved.org_id) as ts:
        user = await ts.get(User, resolved.employee_id)
        if user is None or user.status != "active":
            raise AuthError("xodim topilmadi yoki faol emas")
        phone = user.phone
        user_id, role = user.id, user.role

    code_hash = hashlib.sha256(otp_code.encode()).hexdigest()
    async with plain_session() as session:
        otp = await session.scalar(
            select(OtpCode)
            .where(
                OtpCode.phone == phone,
                OtpCode.code_hash == code_hash,
                OtpCode.consumed_at.is_(None),
                OtpCode.expires_at > datetime.now(UTC),
            )
            .order_by(OtpCode.created_at.desc())
            .limit(1)
        )
        if otp is None:
            raise AuthError("OTP noto'g'ri yoki muddati o'tgan")
        otp.consumed_at = datetime.now(UTC)

        invite = await _load_valid_invite(session, invite_token)
        invite.used_at = datetime.now(UTC)

    async with tenant_session(resolved.org_id) as ts:
        await ts.execute(
            update(Device)
            .where(Device.user_id == user_id, Device.status == "active")
            .values(status="revoked")
        )
        device = Device(
            org_id=resolved.org_id,
            user_id=user_id,
            platform=device_platform,
            fingerprint=device_fingerprint,
            model=device_model,
        )
        ts.add(device)
        await ts.flush()
        device_id = device.id
        # TODO(audit): device_bound hodisasi audit_log'ga + bo'lim boshlig'iga xabar

    return {
        "access_token": issue_token(
            user_id=user_id, org_id=resolved.org_id, role=role, kind="access", device_id=device_id
        ),
        # TODO(v2): rotating refresh + family revocation (refresh_tokens jadvali)
        "refresh_token": issue_token(
            user_id=user_id, org_id=resolved.org_id, role=role, kind="refresh", device_id=device_id
        ),
        "user": {
            "id": str(user_id),
            "role": role,
            "org_id": str(resolved.org_id),
            "org_name": resolved.org_name,
        },
    }
