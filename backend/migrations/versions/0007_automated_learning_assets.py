"""Add private document-derived learning assets and path preferences."""
from alembic import op
import sqlalchemy as sa


revision = "0007_learning_assets"
down_revision = "0006_registration_captcha"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("knowledge_nodes", "knowledge_edges", "quiz_questions"):
        op.add_column(table, sa.Column("owner_id", sa.String(length=36), nullable=True))
        op.create_index(f"ix_{table}_owner_id", table, ["owner_id"])
        op.add_column(table, sa.Column("source_document_id", sa.String(length=36), nullable=True))
        op.create_index(f"ix_{table}_source_document_id", table, ["source_document_id"])

    op.create_table(
        "learning_path_preferences",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", sa.String(length=80), sa.ForeignKey("learning_courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ordered_node_ids", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "course_id", name="uq_learning_path_preference_user_course"),
    )
    op.create_index("ix_learning_path_preferences_user_id", "learning_path_preferences", ["user_id"])
    op.create_index("ix_learning_path_preferences_course_id", "learning_path_preferences", ["course_id"])


def downgrade():
    op.drop_index("ix_learning_path_preferences_course_id", table_name="learning_path_preferences")
    op.drop_index("ix_learning_path_preferences_user_id", table_name="learning_path_preferences")
    op.drop_table("learning_path_preferences")
    for table in ("quiz_questions", "knowledge_edges", "knowledge_nodes"):
        op.drop_index(f"ix_{table}_source_document_id", table_name=table)
        op.drop_column(table, "source_document_id")
        op.drop_index(f"ix_{table}_owner_id", table_name=table)
        op.drop_column(table, "owner_id")
