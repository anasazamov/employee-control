import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, types
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col, uuid_pk

ORG_STATUSES = ("provisioning", "active", "grace", "suspended", "offboarding", "purged")


class Organization(Base):
    """Tenant. RLS'siz — platforma-jadval; app-rol faqat o'z org qatorini o'qiy oladi
    (auth dependency org_id bo'yicha filtrlaydi)."""

    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = uuid_pk()
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="active")
    plan: Mapped[str] = mapped_column(String(32), nullable=False, server_default="trial")
    limits: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    kms_key_id: Mapped[str | None] = mapped_column(String(255))
    ltree_root: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = created_at_col()


class Invite(Base):
    """Aktivatsiya-taklifi. Auth-plane: RLS YO'Q — token bilan org-kontekstsiz topiladi.
    Faqat token_hash saqlanadi; xodimga bog'liq bo'lsa employee_id to'ldiriladi."""

    __tablename__ = "invites"

    id: Mapped[uuid.UUID] = uuid_pk()
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    employee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(8), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(types.TIMESTAMP(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(types.TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = created_at_col()


class OtpCode(Base):
    """SMS OTP (dev'da SMS o'rniga logga yoziladi). Auth-plane: RLS YO'Q."""

    __tablename__ = "otp_codes"

    id: Mapped[uuid.UUID] = uuid_pk()
    phone: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False, server_default="activation")
    expires_at: Mapped[datetime] = mapped_column(types.TIMESTAMP(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(types.TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = created_at_col()
