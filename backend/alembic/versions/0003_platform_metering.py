"""Platforma-metering jadvallari (reja §14): billing_events (append-only usage
hodisalari) + usage_snapshots (kunlik faol-xodim soni/org).

Bular platforma-plane — RLS YO'Q, app_user'ga grant BERILMAYDI. Faqat superuser/
platforma-servis o'qiydi/yozadi (cross-tenant metering).

Revision ID: 0003
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE billing_events (
            id bigserial PRIMARY KEY,
            org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            metric varchar(32) NOT NULL,
            qty integer NOT NULL,
            period_start date NOT NULL,
            recorded_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_billing_events_org ON billing_events (org_id, period_start);
        """
    )
    op.execute(
        """
        CREATE TABLE usage_snapshots (
            id bigserial PRIMARY KEY,
            org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            snapshot_date date NOT NULL,
            active_employees integer NOT NULL,
            checkins integer NOT NULL DEFAULT 0,
            recorded_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_usage_snapshot UNIQUE (org_id, snapshot_date)
        );
        CREATE INDEX ix_usage_snapshots_org ON usage_snapshots (org_id, snapshot_date);
        """
    )
    # app_user'ga grant yo'q — platforma-plane superuser bilan ishlaydi


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS usage_snapshots")
    op.execute("DROP TABLE IF EXISTS billing_events")
