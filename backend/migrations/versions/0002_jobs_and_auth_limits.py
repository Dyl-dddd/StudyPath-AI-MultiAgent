"""Add persistent indexing queue and authentication rate limits."""
from alembic import op
import sqlalchemy as sa

revision = "0002_jobs_and_auth_limits"
down_revision = "0001_legacy_schema"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("auth_rate_limits",
        sa.Column("key", sa.String(64), primary_key=True), sa.Column("window_start", sa.Integer(), nullable=False),
        sa.Column("hits", sa.Integer(), nullable=False))
    op.create_index("ix_auth_rate_limits_window_start", "auth_rate_limits", ["window_start"])
    op.create_table("index_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False), sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_index_jobs_document_id", "index_jobs", ["document_id"])
    op.create_index("ix_index_jobs_status", "index_jobs", ["status"])

def downgrade():
    op.drop_table("index_jobs")
    op.drop_table("auth_rate_limits")
