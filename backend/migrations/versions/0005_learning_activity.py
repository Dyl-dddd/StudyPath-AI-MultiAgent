"""Add learning activity, progress, feedback, notifications and quiz results."""
from alembic import op
import sqlalchemy as sa

revision = "0005_learning_activity"
down_revision = "0004_course_favorites"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("quiz_attempts") as batch:
        batch.add_column(sa.Column("results", sa.JSON(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default="0"))
    op.create_table(
        "study_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", sa.String(80), sa.ForeignKey("learning_courses.id", ondelete="SET NULL"), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("state", sa.String(16), nullable=False, server_default="active"),
    )
    op.create_index("ix_study_sessions_user_id", "study_sessions", ["user_id"])
    op.create_index("ix_study_sessions_course_id", "study_sessions", ["course_id"])
    op.create_index("ix_study_sessions_started_at", "study_sessions", ["started_at"])
    op.create_index("ix_study_sessions_state", "study_sessions", ["state"])
    op.create_table(
        "course_progress",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", sa.String(80), sa.ForeignKey("learning_courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_node_id", sa.String(100), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "course_id", name="uq_course_progress_user_course"),
    )
    op.create_index("ix_course_progress_user_id", "course_progress", ["user_id"])
    op.create_index("ix_course_progress_course_id", "course_progress", ["course_id"])
    op.create_table(
        "knowledge_mastery",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_id", sa.String(100), sa.ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mastery", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "node_id", name="uq_knowledge_mastery_user_node"),
    )
    op.create_index("ix_knowledge_mastery_user_id", "knowledge_mastery", ["user_id"])
    op.create_index("ix_knowledge_mastery_node_id", "knowledge_mastery", ["node_id"])
    op.create_table(
        "user_course_bindings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", sa.String(80), sa.ForeignKey("learning_courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("knowledge_base_id", sa.String(36), sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("user_id", "course_id", name="uq_user_course_kb_binding"),
    )
    op.create_index("ix_user_course_bindings_user_id", "user_course_bindings", ["user_id"])
    op.create_index("ix_user_course_bindings_course_id", "user_course_bindings", ["course_id"])
    op.create_index("ix_user_course_bindings_knowledge_base_id", "user_course_bindings", ["knowledge_base_id"])
    op.create_table(
        "message_feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message_id", sa.String(36), sa.ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rating", sa.String(12), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "message_id", name="uq_message_feedback_user_message"),
    )
    op.create_index("ix_message_feedback_user_id", "message_feedback", ["user_id"])
    op.create_index("ix_message_feedback_message_id", "message_feedback", ["message_id"])
    op.create_table(
        "user_notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_notifications_user_id", "user_notifications", ["user_id"])
    op.create_index("ix_user_notifications_created_at", "user_notifications", ["created_at"])


def downgrade():
    for table in ("user_notifications", "message_feedback", "user_course_bindings", "knowledge_mastery", "course_progress", "study_sessions"):
        op.drop_table(table)
    with op.batch_alter_table("quiz_attempts") as batch:
        batch.drop_column("duration_seconds")
        batch.drop_column("results")
