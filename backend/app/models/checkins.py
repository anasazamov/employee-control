import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Float, ForeignKey, String, types
from sqlalchemy.dialects.postgresql import ARRAY, BYTEA, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, created_at_col, uuid_pk

CHECKIN_VERDICTS = ("pending", "verified", "flagged", "rejected")


class Checkin(Base, TenantMixin):
    """Dalil-yozuv. Append-only: app-rol uchun UPDATE/DELETE granti yo'q (migratsiyada)."""

    __tablename__ = "checkins"

    id: Mapped[uuid.UUID] = uuid_pk()
    assignment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assignments.id", ondelete="SET NULL")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id", ondelete="SET NULL")
    )
    site_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sites.id", ondelete="SET NULL"), index=True
    )
    ts: Mapped[datetime] = mapped_column(types.TIMESTAMP(timezone=True), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    accuracy_m: Mapped[float | None] = mapped_column(Float)
    inside_geofence: Mapped[bool | None] = mapped_column(Boolean)
    selfie_key: Mapped[str | None] = mapped_column(types.Text)
    comment: Mapped[str | None] = mapped_column(types.Text)
    ondevice_score: Mapped[float | None] = mapped_column(Float)
    server_face_score: Mapped[float | None] = mapped_column(Float)
    server_spoof_score: Mapped[float | None] = mapped_column(Float)
    device_integrity: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    risk_score: Mapped[int] = mapped_column(
        types.Integer, nullable=False, server_default="0"
    )
    verdict: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending")
    verdict_reasons: Mapped[list[str] | None] = mapped_column(ARRAY(String(64)))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(types.TIMESTAMP(timezone=True))
    # V2: hash-zanjir
    row_hash: Mapped[bytes | None] = mapped_column(BYTEA)
    prev_hash: Mapped[bytes | None] = mapped_column(BYTEA)
    created_at: Mapped[datetime] = created_at_col()


class FaceEmbedding(Base, TenantMixin):
    """ArcFace 512-o'lchamli embedding; skan HAR DOIM org-filtrli (1:N faqat tenant ichida)."""

    __tablename__ = "face_embeddings"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(512), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, server_default="enrollment")
    quality: Mapped[float | None] = mapped_column(Float)
    model_ver: Mapped[str] = mapped_column(String(64), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = created_at_col()
