import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, ForeignKey, Integer, String, func, types
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BillingEvent(Base):
    """Append-only metering hodisasi (reja §14). Platforma-plane — RLS yo'q."""

    __tablename__ = "billing_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    metric: Mapped[str] = mapped_column(String(32), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        types.TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )


class UsageSnapshot(Base):
    """Kunlik faol-xodim (va check-in) soni — billing asosidagi metrika."""

    __tablename__ = "usage_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    active_employees: Mapped[int] = mapped_column(Integer, nullable=False)
    checkins: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    recorded_at: Mapped[datetime] = mapped_column(
        types.TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
