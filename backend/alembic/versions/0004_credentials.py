"""Username/parol auth — credentials jadval (auth-plane, RLS'siz).

Login org-kontekstsiz username bo'yicha topilishi kerak (invites/otp_codes kabi),
shuning uchun RLS YO'Q. username global-unikal. app_user SELECT/INSERT/UPDATE oladi.

Revision ID: 0004
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE credentials (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            username varchar(128) NOT NULL UNIQUE,
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            password_hash varchar(255) NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz
        );
        CREATE INDEX ix_credentials_user_id ON credentials (user_id);
        """
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON credentials TO app_user")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS credentials")
