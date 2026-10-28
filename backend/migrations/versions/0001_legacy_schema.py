"""Baseline the existing StudyPath schema."""
from alembic import op
import sqlalchemy as sa

revision = "0001_legacy_schema"
down_revision = None
branch_labels = None
depends_on = None
LEGACY_TABLES = ("users", "knowledge_bases", "documents", "document_chunks", "chat_sessions", "chat_messages", "message_citations")

def upgrade():
    op.create_table("users",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("username", sa.String(48), nullable=False),
        sa.Column("password_hash", sa.String(256), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_table("knowledge_bases",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False), sa.Column("course_name", sa.String(120), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_knowledge_bases_owner_id", "knowledge_bases", ["owner_id"])
    op.create_table("documents",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("knowledge_base_id", sa.String(36), sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False), sa.Column("storage_name", sa.String(80), nullable=False),
        sa.Column("file_type", sa.String(10), nullable=False), sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False), sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False), sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "knowledge_base_id", "file_hash", name="uq_document_hash_per_kb"),
        sa.UniqueConstraint("storage_name"))
    op.create_index("ix_documents_owner_id", "documents", ["owner_id"])
    op.create_index("ix_documents_knowledge_base_id", "documents", ["knowledge_base_id"])
    op.create_index("ix_documents_status", "documents", ["status"])
    op.create_table("document_chunks",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("knowledge_base_id", sa.String(36), sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False), sa.Column("page_start", sa.Integer(), nullable=True), sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("section_title", sa.String(500), nullable=False), sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False), sa.Column("content_hash", sa.String(64), nullable=False), sa.Column("model_version", sa.String(180), nullable=False))
    for column in ("document_id", "knowledge_base_id", "owner_id"):
        op.create_index(f"ix_document_chunks_{column}", "document_chunks", [column])
    op.create_table("chat_sessions",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("knowledge_base_id", sa.String(36), sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(180), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_chat_sessions_owner_id", "chat_sessions", ["owner_id"])
    op.create_index("ix_chat_sessions_knowledge_base_id", "chat_sessions", ["knowledge_base_id"])
    op.create_table("chat_messages",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("session_id", sa.String(36), sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(16), nullable=False), sa.Column("content", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id"])
    op.create_table("message_citations",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("message_id", sa.String(36), sa.ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_id", sa.String(36), sa.ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=False), sa.Column("score", sa.Double(), nullable=False))
    for column in ("message_id", "document_id", "chunk_id"):
        op.create_index(f"ix_message_citations_{column}", "message_citations", [column])

def downgrade():
    for table in reversed(LEGACY_TABLES):
        op.drop_table(table)
