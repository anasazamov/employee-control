import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.sql import text

from app.config import get_settings

_engine = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine():
    global _engine, _sessionmaker
    if _engine is None:
        _engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    get_engine()
    assert _sessionmaker is not None
    return _sessionmaker


async def set_org_guc(session: AsyncSession, org_id: uuid.UUID) -> None:
    """Tranzaksiya doirasida tenant-kontekstni o'rnatadi — RLS shu GUC'ga tayanadi.

    SET LOCAL parametrlashtirilmaydi, shuning uchun qiymat UUID ekani majburan
    tekshirilib, literal sifatida qo'yiladi.
    """
    org_literal = str(uuid.UUID(str(org_id)))
    await session.execute(text(f"SET LOCAL app.org_id = '{org_literal}'"))


@asynccontextmanager
async def tenant_session(org_id: uuid.UUID) -> AsyncIterator[AsyncSession]:
    """Bitta tranzaksiya = bitta tenant-kontekst. Chiqishda commit, xatoda rollback."""
    async with get_sessionmaker()() as session:
        async with session.begin():
            await set_org_guc(session, org_id)
            yield session


@asynccontextmanager
async def plain_session() -> AsyncIterator[AsyncSession]:
    """Tenant-konteksтsiz sessiya — faqat auth-plane jadvallar (invites, otp_codes)
    va RLS'siz o'qishlar uchun. Tenant-jadvallarda GUC'siz so'rov nol qator qaytaradi."""
    async with get_sessionmaker()() as session:
        async with session.begin():
            yield session
