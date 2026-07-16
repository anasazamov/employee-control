"""Checkins uchun USTUN-darajali UPDATE grantlari.

0001'da checkins to'liq append-only edi. Verdikt-hayotsikli (review, yuz-worker
natijalari) va izoh-append uchun FAQAT lifecycle-ustunlarga UPDATE ochiladi.
Dalil-ustunlar (ts, lat, lon, accuracy_m, user_id, device_id, site_id,
device_integrity, ondevice_score, row_hash, prev_hash...) app_user uchun
QULFLANGAN qoladi — admin ham tarixdagi faktni o'zgartira olmaydi (reja §5, §13).

Revision ID: 0002
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

LIFECYCLE_COLUMNS = (
    "verdict",
    "verdict_reasons",
    "reviewed_by",
    "reviewed_at",
    "server_face_score",
    "server_spoof_score",
    "selfie_key",
    "comment",
    "risk_score",
)


def upgrade() -> None:
    op.execute("ALTER TABLE checkins ADD COLUMN risk_score integer NOT NULL DEFAULT 0")
    cols = ", ".join(LIFECYCLE_COLUMNS)
    op.execute(f"GRANT UPDATE ({cols}) ON checkins TO app_user")


def downgrade() -> None:
    op.execute("REVOKE UPDATE ON checkins FROM app_user")
    op.execute("ALTER TABLE checkins DROP COLUMN risk_score")
