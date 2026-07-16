import uuid
from datetime import datetime

from geoalchemy2 import Geography
from sqlalchemy import Boolean, Float, SmallInteger, String, types
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin


class LocationPoint(Base, TenantMixin):
    """Timescale hypertable (migratsiyada aylantiriladi). PK yo'q — (point_uuid, ts)
    unikal indeksi idempotent batch-ingestion uchun (hypertable'da unikal indeks
    partitsiya-ustuni ts'ni o'z ichiga olishi shart)."""

    __tablename__ = "location_points"

    ts: Mapped[datetime] = mapped_column(
        types.TIMESTAMP(timezone=True), primary_key=True, nullable=False
    )
    point_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    device_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    geog: Mapped[object] = mapped_column(Geography("POINT", srid=4326), nullable=False)
    accuracy_m: Mapped[float | None] = mapped_column(Float)
    speed_mps: Mapped[float | None] = mapped_column(Float)
    heading: Mapped[float | None] = mapped_column(Float)
    battery: Mapped[int | None] = mapped_column(SmallInteger)
    is_mock: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    provider: Mapped[str | None] = mapped_column(String(32))
