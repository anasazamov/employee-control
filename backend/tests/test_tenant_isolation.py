"""Tenant-izolyatsiya testlari (reja §19 — CI-majburiy).

Barcha testlar app_user (RLS'ni chetlab o'tolmaydigan rol) bilan ulanadi;
admin_session faqat ma'lumot tayyorlashda ishlatiladi.
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError, ProgrammingError

from app.db import plain_session, tenant_session
from app.models import Checkin, User


async def test_no_guc_returns_zero_rows(seed, admin_session):
    """RLS smoke: GUC o'rnatilmagan sessiya tenant-jadvaldan NOL qator ko'radi —
    ma'lumot mavjud bo'lsa ham (admin buni tasdiqlaydi)."""
    admin_count = await admin_session.scalar(select(func.count()).select_from(User))
    assert admin_count >= 2  # ikkala org owner'i bor

    async with plain_session() as s:
        app_count = await s.scalar(select(func.count()).select_from(User))
    assert app_count == 0


async def test_tenant_sees_only_own_rows(seed):
    async with tenant_session(seed.org1.org_id) as s:
        users = (await s.scalars(select(User))).all()
    assert len(users) >= 1
    assert all(u.org_id == seed.org1.org_id for u in users)
    phones = {u.phone for u in users}
    assert seed.org2.owner_phone not in phones


async def test_cross_tenant_insert_rejected(seed):
    """org1-kontekstda org2 uchun yozuv WITH CHECK bilan rad etiladi."""
    with pytest.raises((DBAPIError, ProgrammingError)):
        async with tenant_session(seed.org1.org_id) as s:
            s.add(
                User(
                    org_id=seed.org2.org_id,
                    full_name="Hacker",
                    phone="+998911111111",
                )
            )
            await s.flush()


async def test_cross_tenant_update_invisible(seed):
    """org1-kontekstda org2 qatorini UPDATE qilish 0 qatorga tegadi (ko'rinmaydi)."""
    from sqlalchemy import update

    async with tenant_session(seed.org1.org_id) as s:
        result = await s.execute(
            update(User)
            .where(User.id == seed.org2.owner_id)
            .values(full_name="O'zgartirilgan")
        )
    assert result.rowcount == 0


async def test_checkins_append_only(seed, admin_session):
    """Dalil-jadval: app_user uchun UPDATE granti yo'q — permission denied."""
    checkin_id = uuid.uuid4()
    admin_session.add(
        Checkin(
            id=checkin_id,
            org_id=seed.org1.org_id,
            user_id=seed.org1.owner_id,
            ts=datetime.now(UTC),
            lat=41.3111,
            lon=69.2797,
        )
    )
    await admin_session.flush()
    # admin_session tranzaksiyasi ochiq — app ko'rishi uchun commit qilamiz
    await admin_session.commit()

    from sqlalchemy import update

    with pytest.raises((DBAPIError, ProgrammingError)) as exc_info:
        async with tenant_session(seed.org1.org_id) as s:
            await s.execute(
                update(Checkin).where(Checkin.id == checkin_id).values(comment="tahrir")
            )
    assert "permission denied" in str(exc_info.value).lower()

    # INSERT esa ruxsat etilgan (append-only'ning "append" qismi)
    async with tenant_session(seed.org1.org_id) as s:
        s.add(
            Checkin(
                org_id=seed.org1.org_id,
                user_id=seed.org1.owner_id,
                ts=datetime.now(UTC),
                lat=41.32,
                lon=69.28,
            )
        )
        await s.flush()


async def test_provision_idempotent(seed, admin_session):
    from app.modules.tenancy.service import provision_tenant

    r = await provision_tenant(
        admin_session,
        name="Test Org 1 (takror)",
        slug="test-org-1",
        owner_phone="+998900000001",
    )
    assert r.created is False
    assert r.org.id == seed.org1.org_id
    assert r.invite_token is None
