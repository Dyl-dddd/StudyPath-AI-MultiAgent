"""Persist per-account favorite courses."""
from alembic import op
import sqlalchemy as sa

revision = "0004_course_favorites"
down_revision = "0003_learning_workspace"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("user_profiles", sa.Column("favorite_course_ids", sa.JSON(), nullable=False, server_default="[]"))


def downgrade():
    op.drop_column("user_profiles", "favorite_course_ids")
