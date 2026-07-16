import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint, types
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Ltree, TenantMixin, created_at_col, uuid_pk

USER_ROLES = ("org_admin", "hr", "dept_head", "field_employee")


class Department(Base, TenantMixin):
    __tablename__ = "departments"
    __table_args__ = (
        UniqueConstraint("path", name="uq_departments_path"),
        Index("ix_departments_path_gist", "path", postgresql_using="gist"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Org-ildizli yo'l: o_{shortid}.boshqarma.bolim
    path: Mapped[str] = mapped_column(Ltree(), nullable=False)
    head_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL", use_alter=True)
    )
    created_at: Mapped[datetime] = created_at_col()


class User(Base, TenantMixin):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("org_id", "phone", name="uq_users_org_phone"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL")
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False, server_default="field_employee")
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Telefon TENANT ichida unikal (pudratchi ikki org'da bo'lishi mumkin)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    employee_no: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="active")
    attributes: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    face_enrolled_at: Mapped[datetime | None] = mapped_column(types.TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = created_at_col()


class UserScopeGrant(Base, TenantMixin):
    """Qo'shimcha ko'rish doiralari (masalan, HR bir nechta filialni ko'radi)."""

    __tablename__ = "user_scope_grants"
    __table_args__ = (UniqueConstraint("user_id", "department_path", name="uq_scope_grant"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    department_path: Mapped[str] = mapped_column(Ltree(), nullable=False)
    granted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = created_at_col()


class Device(Base, TenantMixin):
    """Bog'langan qurilma. 1 faol qurilma/(org, xodim) — partial unique migratsiyada."""

    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[str] = mapped_column(String(16), nullable=False)
    model: Mapped[str | None] = mapped_column(String(128))
    fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    pubkey: Mapped[str | None] = mapped_column(types.Text)
    push_token: Mapped[str | None] = mapped_column(types.Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="active")
    bound_at: Mapped[datetime] = created_at_col()
    last_seen_at: Mapped[datetime | None] = mapped_column(types.TIMESTAMP(timezone=True))


class Shift(Base, TenantMixin):
    """Smena — tracking faqat shu oraliqda yoqiladi."""

    __tablename__ = "shifts"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    starts_at: Mapped[datetime] = mapped_column(types.TIMESTAMP(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(types.TIMESTAMP(timezone=True), nullable=False)
    created_at: Mapped[datetime] = created_at_col()
