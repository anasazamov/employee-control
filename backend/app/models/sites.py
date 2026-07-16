import uuid
from datetime import datetime

from geoalchemy2 import Geography, Geometry
from sqlalchemy import ForeignKey, Integer, String, types
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, created_at_col, uuid_pk


class SiteType(Base, TenantMixin):
    """Tenant-belgilaydigan obyekt turlari (shablondan seed qilinadi)."""

    __tablename__ = "site_types"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = created_at_col()


class Site(Base, TenantMixin):
    """Obyekt: geofence polygon YOKI markaz+radius (default 150 m)."""

    __tablename__ = "sites"

    id: Mapped[uuid.UUID] = uuid_pk()
    site_type_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("site_types.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(types.Text)
    geom: Mapped[object | None] = mapped_column(Geometry("POLYGON", srid=4326))
    center: Mapped[object] = mapped_column(Geography("POINT", srid=4326), nullable=False)
    radius_m: Mapped[int] = mapped_column(Integer, nullable=False, server_default="150")
    min_dwell_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="15")
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="active")
    attributes: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = created_at_col()


class Assignment(Base, TenantMixin):
    __tablename__ = "assignments"

    id: Mapped[uuid.UUID] = uuid_pk()
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    due_from: Mapped[datetime | None] = mapped_column(types.TIMESTAMP(timezone=True))
    due_to: Mapped[datetime | None] = mapped_column(types.TIMESTAMP(timezone=True))
    # V2: kech-ochish — inspektor topshiriqni shu vaqtdan keyin ko'radi
    reveal_at: Mapped[datetime | None] = mapped_column(types.TIMESTAMP(timezone=True))
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending")
    min_dwell_minutes: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = created_at_col()


class SitePresence(Base, TenantMixin):
    """Jonli obyekt-bandlik: kim qaysi obyektda (exited_at NULL = hozir ichkarida)."""

    __tablename__ = "site_presence"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entered_at: Mapped[datetime] = mapped_column(types.TIMESTAMP(timezone=True), nullable=False)
    exited_at: Mapped[datetime | None] = mapped_column(types.TIMESTAMP(timezone=True))
    dwell_seconds: Mapped[int | None] = mapped_column(Integer)
