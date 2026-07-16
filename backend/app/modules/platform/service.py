"""Platforma-servis (reja §14). Superuser-sessiya bilan ishlaydi — RLS'ni chetlab
o'tadi (cross-tenant metering/boshqaruv), shuning uchun bu modul FAQAT platforma-
kaliti bilan himoyalangan endpoint'lardan chaqiriladi (router.py).

Provisioning tenancy.provision_tenant'ni qayta ishlatadi; status/plan o'zgarishi
org-status keshini darhol tozalaydi (suspension-gate uchun)."""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models import BillingEvent, Checkin, Organization, UsageSnapshot, User
from app.modules.tenancy.service import provision_tenant
from app.modules.tenancy.status import invalidate_status

_ACTIVE_USER_STATUSES = ("active", "suspended")  # arxivlanmagan = billing-faol


@asynccontextmanager
async def platform_session() -> AsyncIterator[AsyncSession]:
    """Superuser-sessiya — RLS'siz, barcha tenantlar ko'rinadi. Faqat platforma-plane."""
    url = get_settings().migrations_database_url.replace("+psycopg", "+asyncpg")
    engine = create_async_engine(url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as s:
            async with s.begin():
                yield s
    finally:
        await engine.dispose()


@dataclass
class TenantRow:
    id: str
    slug: str
    name: str
    status: str
    plan: str
    employees: int


async def list_tenants() -> list[TenantRow]:
    async with platform_session() as s:
        counts = dict(
            (
                await s.execute(
                    select(User.org_id, func.count())
                    .where(User.status.in_(_ACTIVE_USER_STATUSES))
                    .group_by(User.org_id)
                )
            ).all()
        )
        orgs = (await s.scalars(select(Organization).order_by(Organization.created_at))).all()
        return [
            TenantRow(
                id=str(o.id),
                slug=o.slug,
                name=o.name,
                status=o.status,
                plan=o.plan,
                employees=counts.get(o.id, 0),
            )
            for o in orgs
        ]


async def provision(
    *, name: str, slug: str, owner_phone: str, owner_name: str, plan: str
) -> dict:
    async with platform_session() as s:
        r = await provision_tenant(
            s, name=name, slug=slug, owner_phone=owner_phone, owner_name=owner_name
        )
        if r.created and plan != "trial":
            r.org.plan = plan
        return {
            "org_id": str(r.org.id),
            "slug": r.org.slug,
            "created": r.created,
            "invite_token": r.invite_token,
            "invite_code": r.invite_code,
        }


async def update_tenant(
    org_id: uuid.UUID, *, status: str | None, plan: str | None
) -> TenantRow | None:
    async with platform_session() as s:
        org = await s.get(Organization, org_id)
        if org is None:
            return None
        if status is not None:
            org.status = status
        if plan is not None:
            org.plan = plan
        await s.flush()
        emp = await s.scalar(
            select(func.count())
            .select_from(User)
            .where(User.org_id == org_id, User.status.in_(_ACTIVE_USER_STATUSES))
        )
        row = TenantRow(
            id=str(org.id),
            slug=org.slug,
            name=org.name,
            status=org.status,
            plan=org.plan,
            employees=emp or 0,
        )
    # Kesh tozalash tranzaksiyadan TASHQARIDA — suspension-gate darhol ko'radi
    if status is not None:
        await invalidate_status(org_id)
    return row


async def snapshot_usage(snapshot_date: date) -> int:
    """Har org uchun faol-xodim + o'sha kungi check-in sonini yozadi (idempotent
    upsert). billing_events'ga 'active_employees' metrikasi qo'shiladi. Kunlik beat-job.
    Qaytaradi: qayta ishlangan tenant soni."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    async with platform_session() as s:
        emp_counts = dict(
            (
                await s.execute(
                    select(User.org_id, func.count())
                    .where(User.status.in_(_ACTIVE_USER_STATUSES))
                    .group_by(User.org_id)
                )
            ).all()
        )
        ck_counts = dict(
            (
                await s.execute(
                    select(Checkin.org_id, func.count())
                    .where(func.date(Checkin.ts) == snapshot_date)
                    .group_by(Checkin.org_id)
                )
            ).all()
        )
        org_ids = (await s.scalars(select(Organization.id))).all()
        for oid in org_ids:
            active = emp_counts.get(oid, 0)
            checkins = ck_counts.get(oid, 0)
            await s.execute(
                pg_insert(UsageSnapshot)
                .values(
                    org_id=oid,
                    snapshot_date=snapshot_date,
                    active_employees=active,
                    checkins=checkins,
                )
                .on_conflict_do_update(
                    index_elements=["org_id", "snapshot_date"],
                    set_={"active_employees": active, "checkins": checkins},
                )
            )
            s.add(
                BillingEvent(
                    org_id=oid,
                    metric="active_employees",
                    qty=active,
                    period_start=snapshot_date.replace(day=1),
                )
            )
        return len(org_ids)
