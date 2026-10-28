from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from app.core.config import BACKEND_DIR
from app.core.db import engine

LEGACY_TABLES = {"users", "knowledge_bases", "documents", "document_chunks", "chat_sessions", "chat_messages", "message_citations"}

def upgrade_database() -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    tables = set(inspect(engine).get_table_names())
    if "alembic_version" not in tables:
        app_tables = tables - {"sqlite_sequence"}
        if app_tables and not LEGACY_TABLES.issubset(app_tables):
            missing = ", ".join(sorted(LEGACY_TABLES - app_tables))
            raise RuntimeError(f"Database schema is incomplete; missing legacy tables: {missing}")
        if LEGACY_TABLES.issubset(app_tables):
            command.stamp(config, "0001_legacy_schema")
    command.upgrade(config, "head")
