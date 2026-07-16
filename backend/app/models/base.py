import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, MetaData, func, types
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Ltree(types.UserDefinedType):
    """Postgres ltree ustuni uchun minimal tip (qo'shimcha kutubxonasiz)."""

    cache_ok = True

    def get_col_spec(self, **kw) -> str:
        return "ltree"

    def bind_processor(self, dialect):
        def process(value):
            return str(value) if value is not None else None

        return process

    def result_processor(self, dialect, coltype):
        def process(value):
            return value

        return process


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )


def created_at_col() -> Mapped[datetime]:
    return mapped_column(types.TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)


class TenantMixin:
    """Har tenant-jadval org_id olib yuradi; RLS shu ustunga bog'langan."""

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
