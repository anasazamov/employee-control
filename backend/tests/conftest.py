"""Test-infratuzilma.

Talab: docker compose -f infra/docker-compose.dev.yml up -d db  (real PostgreSQL —
RLS/Timescale/pgvector mock qilinmaydi, reja §19: izolyatsiya-testlar CI-majburiy).

Sxema har test-sessiyada toza quriladi (downgrade base → upgrade head),
so'ng ikkita test-tenant provision qilinadi.
"""

import asyncio
import uuid
from dataclasses import dataclass

import pytest
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from alembic import command
from app.config import get_settings
from app.modules.tenancy.service import provision_tenant

BACKEND_DIR = __file__.rsplit("tests", 1)[0]


@dataclass
class SeededOrg:
    org_id: uuid.UUID
    owner_id: uuid.UUID
    owner_phone: str
    invite_token: str
    invite_code: str


@dataclass
class Seed:
    org1: SeededOrg
    org2: SeededOrg


def _admin_engine() -> AsyncEngine:
    url = get_settings().migrations_database_url.replace("+psycopg", "+asyncpg")
    return create_async_engine(url)


async def _seed() -> Seed:
    engine = _admin_engine()
    try:
        maker = async_sessionmaker(engine, expire_on_commit=False)
        orgs: list[SeededOrg] = []
        for i in (1, 2):
            async with maker() as session:
                async with session.begin():
                    r = await provision_tenant(
                        session,
                        name=f"Test Org {i}",
                        slug=f"test-org-{i}",
                        owner_phone=f"+99890000000{i}",
                        owner_name=f"Owner {i}",
                    )
                    assert r.created and r.invite_token and r.invite_code
                    orgs.append(
                        SeededOrg(
                            org_id=r.org.id,
                            owner_id=r.owner.id,
                            owner_phone=r.owner.phone,
                            invite_token=r.invite_token,
                            invite_code=r.invite_code,
                        )
                    )
        return Seed(org1=orgs[0], org2=orgs[1])
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def seed() -> Seed:
    cfg = Config(BACKEND_DIR + "alembic.ini")
    cfg.set_main_option("script_location", BACKEND_DIR + "alembic")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    return asyncio.run(_seed())


@pytest.fixture(autouse=True)
async def _reset_global_engine():
    """Har test o'z event-loop'ida — global engine'ni testlar orasida tozalaymiz."""
    yield
    import app.db as dbmod

    if dbmod._engine is not None:
        await dbmod._engine.dispose()
        dbmod._engine = None
        dbmod._sessionmaker = None


@pytest.fixture
async def admin_session():
    """Superuser-sessiya (RLS'ni chetlab o'tadi) — test-ma'lumot tayyorlash uchun.
    Tranzaksiyani test o'zi boshqaradi (flush/commit); teardown'da ochiq tx rollback."""
    engine = _admin_engine()
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with maker() as session:
            yield session
            await session.rollback()
    finally:
        await engine.dispose()
