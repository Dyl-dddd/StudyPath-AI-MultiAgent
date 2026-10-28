"""Allow knowledge-base and general-model chat sessions."""
from alembic import op
import sqlalchemy as sa


revision = "0009_chat_answer_modes"
down_revision = "0008_mistake_variant_sets"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("chat_sessions") as batch_op:
        batch_op.alter_column(
            "knowledge_base_id",
            existing_type=sa.String(length=36),
            nullable=True,
        )
        batch_op.add_column(sa.Column("answer_mode", sa.String(length=20), nullable=False, server_default="library"))


def downgrade():
    with op.batch_alter_table("chat_sessions") as batch_op:
        batch_op.drop_column("answer_mode")
        batch_op.alter_column(
            "knowledge_base_id",
            existing_type=sa.String(length=36),
            nullable=False,
        )
