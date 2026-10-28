"""Persist profiles, course catalog, plans, quiz history and mistakes."""
from alembic import op
import sqlalchemy as sa

revision = "0003_learning_workspace"
down_revision = "0002_jobs_and_auth_limits"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False), sa.Column("school", sa.String(160), nullable=False),
        sa.Column("major", sa.String(120), nullable=False), sa.Column("grade", sa.String(30), nullable=False),
        sa.Column("bio", sa.Text(), nullable=False), sa.Column("weekly_goal_hours", sa.Integer(), nullable=False),
        sa.Column("daily_focus_hours", sa.Integer(), nullable=False), sa.Column("learning_reminders", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "learning_courses",
        sa.Column("id", sa.String(80), primary_key=True), sa.Column("name", sa.String(160), nullable=False),
        sa.Column("category", sa.String(80), nullable=False), sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("chapter", sa.String(240), nullable=False), sa.Column("color", sa.String(20), nullable=False),
        sa.Column("icon", sa.String(20), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "knowledge_nodes",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("course_id", sa.String(80), sa.ForeignKey("learning_courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(180), nullable=False), sa.Column("type", sa.String(24), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
    )
    op.create_index("ix_knowledge_nodes_course_id", "knowledge_nodes", ["course_id"])
    op.create_table(
        "knowledge_edges",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("course_id", sa.String(80), sa.ForeignKey("learning_courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(100), sa.ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target", sa.String(100), sa.ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("course_id", "source", "target", name="uq_knowledge_edge"),
    )
    op.create_index("ix_knowledge_edges_course_id", "knowledge_edges", ["course_id"])
    op.create_index("ix_knowledge_edges_source", "knowledge_edges", ["source"])
    op.create_index("ix_knowledge_edges_target", "knowledge_edges", ["target"])
    op.create_table(
        "quiz_questions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("course_id", sa.String(80), sa.ForeignKey("learning_courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(30), nullable=False), sa.Column("difficulty", sa.String(30), nullable=False),
        sa.Column("topic", sa.String(160), nullable=False), sa.Column("concept_id", sa.String(100), nullable=False),
        sa.Column("title", sa.Text(), nullable=False), sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("answer", sa.JSON(), nullable=False), sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("misconceptions", sa.JSON(), nullable=False), sa.Column("transfer_question_ids", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=True),
    )
    op.create_index("ix_quiz_questions_course_id", "quiz_questions", ["course_id"])
    op.create_table(
        "study_tasks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(240), nullable=False), sa.Column("course", sa.String(160), nullable=False),
        sa.Column("date", sa.String(80), nullable=False), sa.Column("priority", sa.String(8), nullable=False),
        sa.Column("done", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_study_tasks_user_id", "study_tasks", ["user_id"])
    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", sa.String(80), nullable=False), sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("question_count", sa.Integer(), nullable=False), sa.Column("answers", sa.JSON(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_quiz_attempts_user_id", "quiz_attempts", ["user_id"])
    op.create_index("ix_quiz_attempts_at", "quiz_attempts", ["at"])
    op.create_table(
        "user_mistakes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False), sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "question_id", name="uq_user_mistake"),
    )
    op.create_index("ix_user_mistakes_user_id", "user_mistakes", ["user_id"])
    op.create_index("ix_user_mistakes_question_id", "user_mistakes", ["question_id"])


def downgrade():
    op.drop_table("user_mistakes")
    op.drop_table("quiz_attempts")
    op.drop_table("study_tasks")
    op.drop_table("quiz_questions")
    op.drop_table("knowledge_edges")
    op.drop_table("knowledge_nodes")
    op.drop_table("learning_courses")
    op.drop_table("user_profiles")
