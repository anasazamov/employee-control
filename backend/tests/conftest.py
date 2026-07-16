"""Test-infratuzilma.

Talab: docker compose -f infra/docker-compose.dev.yml up -d db  (real PostgreSQL —
RLS/Timescale/pgvector mock qilinmaydi, reja §19: izolyatsiya-testlar CI-majburiy).

Sxema har test-sessiyada toza quriladi (downgrade base → upgrade head),
so'ng ikkita test-tenant provision qilinadi.
"""

import asyncio
import os
import uuid
from dataclasses import dataclass

# Testlar alohida Redis DB (15) ishlatadi — dev-ma'lumot (db 0) flush bo'lmasligi uchun.
# app.config import qilinishidan OLDIN o'rnatilishi shart (Settings lru_cache).
os.environ.setdefault("EC_REDIS_URL", "redis://localhost:6380/15")

import pytest
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from alembic import command
from app.config import get_settings
from app.modules.auth.security import issue_token
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


async def _flush_test_redis() -> None:
    import redis.asyncio as aioredis

    r = aioredis.from_url(get_settings().redis_url)
    try:
        await r.flushdb()
    finally:
        await r.aclose()


@pytest.fixture(scope="session")
def seed() -> Seed:
    cfg = Config(BACKEND_DIR + "alembic.ini")
    cfg.set_main_option("script_location", BACKEND_DIR + "alembic")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    asyncio.run(_flush_test_redis())
    return asyncio.run(_seed())


def make_access_token(
    org: SeededOrg, role: str = "org_admin", device_id: uuid.UUID | None = None
) -> str:
    return issue_token(
        user_id=org.owner_id, org_id=org.org_id, role=role, kind="access", device_id=device_id
    )


def auth_header(
    org: SeededOrg, role: str = "org_admin", device_id: uuid.UUID | None = None
) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_access_token(org, role, device_id)}"}


@pytest.fixture(autouse=True)
async def _reset_global_clients():
    """Har test o'z event-loop'ida — loop'ga bog'langan global mijozlar (engine, redis)
    testlar orasida tozalanadi."""
    yield
    import app.db as dbmod
    import app.redis as rmod

    if dbmod._engine is not None:
        await dbmod._engine.dispose()
        dbmod._engine = None
        dbmod._sessionmaker = None
    if rmod._client is not None:
        await rmod._client.aclose()
        rmod._client = None


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
