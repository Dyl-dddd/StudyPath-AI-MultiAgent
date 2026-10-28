"""Store generated mistake practice sets without exposing answer keys."""
from alembic import op
import sqlalchemy as sa


revision = "0008_mistake_variant_sets"
down_revision = "0007_learning_assets"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "mistake_variant_sets",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_question_id", sa.Integer(), nullable=False),
        sa.Column("variants", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_mistake_variant_sets_user_id", "mistake_variant_sets", ["user_id"])
    op.create_index("ix_mistake_variant_sets_source_question_id", "mistake_variant_sets", ["source_question_id"])
    op.create_index("ix_mistake_variant_sets_expires_at", "mistake_variant_sets", ["expires_at"])


def downgrade():
    op.drop_index("ix_mistake_variant_sets_expires_at", table_name="mistake_variant_sets")
    op.drop_index("ix_mistake_variant_sets_source_question_id", table_name="mistake_variant_sets")
    op.drop_index("ix_mistake_variant_sets_user_id", table_name="mistake_variant_sets")
    op.drop_table("mistake_variant_sets")
