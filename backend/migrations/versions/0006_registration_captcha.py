"""Add persisted, one-time registration CAPTCHA challenges."""
from alembic import op
import sqlalchemy as sa


revision = "0006_registration_captcha"
down_revision = "0005_learning_activity"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "captcha_challenges",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("answer_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.Integer(), nullable=False),
    )
    op.create_index("ix_captcha_challenges_expires_at", "captcha_challenges", ["expires_at"])
    op.create_index("ix_captcha_challenges_created_at", "captcha_challenges", ["created_at"])


def downgrade():
    op.drop_index("ix_captcha_challenges_created_at", table_name="captcha_challenges")
    op.drop_index("ix_captcha_challenges_expires_at", table_name="captcha_challenges")
    op.drop_table("captcha_challenges")
