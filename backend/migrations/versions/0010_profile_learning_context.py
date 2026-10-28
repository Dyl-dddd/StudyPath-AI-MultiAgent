"""Add editable education-stage and learning-goal context to user profiles."""
from alembic import op
import sqlalchemy as sa


revision = "0010_profile_learning_context"
down_revision = "0009_chat_answer_modes"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user_profiles") as batch_op:
        batch_op.add_column(sa.Column("education_stage", sa.String(length=24), nullable=False, server_default="大学"))
        batch_op.add_column(sa.Column("learning_subjects", sa.JSON(), nullable=False, server_default="[]"))
        batch_op.add_column(sa.Column("learning_goal", sa.Text(), nullable=False, server_default=""))


def downgrade():
    with op.batch_alter_table("user_profiles") as batch_op:
        batch_op.drop_column("learning_goal")
        batch_op.drop_column("learning_subjects")
        batch_op.drop_column("education_stage")
