import uuid
from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, String, func, types
from sqlalchemy.dialects.postgresql import BYTEA, INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, created_at_col, uuid_pk


class AuditLog(Base, TenantMixin):
    """Append-only: har admin-amal trigger yoki servis orqali shu yerga."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(
        types.TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    object_type: Mapped[str | None] = mapped_column(String(64))
    object_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    ip: Mapped[str | None] = mapped_column(INET)
    # V2: hash-zanjir
    row_hash: Mapped[bytes | None] = mapped_column(BYTEA)
    prev_hash: Mapped[bytes | None] = mapped_column(BYTEA)


class AccessLog(Base, TenantMixin):
    """Kuzatuvchilarni kuzatish: kim kimning lokatsiya/selfie/tarixini ko'rdi."""

    __tablename__ = "access_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(
        types.TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    viewer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    resource: Mapped[str] = mapped_column(String(64), nullable=False)
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")


class Consent(Base, TenantMixin):
    """Biometrik rozilik — shablon-versiyasi bilan."""

    __tablename__ = "consents"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    template_version: Mapped[str] = mapped_column(String(32), nullable=False)
    signed_at: Mapped[datetime] = created_at_col()
    withdrawn_at: Mapped[datetime | None] = mapped_column(types.TIMESTAMP(timezone=True))
