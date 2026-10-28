"""Restore a local StudyPath backup after validating archive paths and SQLite."""
import argparse
import shutil
import sqlite3
import stat
import tempfile
import time
import zipfile
from pathlib import Path, PurePosixPath
from app.core.config import DATA_DIR, get_settings
from scripts.backup_data import database_file, local_qdrant_path, create_backup

ALLOWED_PREFIXES = ("database/studypath.db", "data/uploads/", "data/qdrant/", "data/auth.secret")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--service-stopped", action="store_true", help="confirm API and workers are stopped")
    parser.add_argument("--confirm-restore", action="store_true", help="allow replacing local runtime data")
    args = parser.parse_args()
    if not args.service_stopped or not args.confirm_restore:
        raise SystemExit("Stop all StudyPath processes and pass both --service-stopped and --confirm-restore")
    if not get_settings().database_url.startswith("sqlite:"):
        raise SystemExit("Remote PostgreSQL restore is not supported by this script; use pg_restore")
    if get_settings().qdrant_url:
        raise SystemExit("Remote Qdrant restore requires a Qdrant snapshot; this script only restores local Qdrant")
    db_path = database_file()
    if db_path is None:
        raise SystemExit("Could not resolve SQLite database path")
    with zipfile.ZipFile(args.archive) as archive:
        names = archive.namelist()
        for member in archive.infolist():
            name = member.filename
            path = PurePosixPath(name)
            mode = member.external_attr >> 16
            if "\\" in name or stat.S_ISLNK(mode) or path.is_absolute() or ".." in path.parts or not any(name == prefix or name.startswith(prefix) for prefix in ALLOWED_PREFIXES):
                raise SystemExit(f"Unexpected or unsafe archive member: {name}")
        database_member = "database/studypath.db"
        if database_member not in names:
            raise SystemExit("Backup has no database/studypath.db")
        with tempfile.TemporaryDirectory(prefix="studypath-restore-") as temp:
            temp_root = Path(temp)
            archive.extractall(temp_root)
            candidate_db = temp_root / database_member
            connection = sqlite3.connect(candidate_db)
            try:
                result = connection.execute("PRAGMA integrity_check").fetchone()[0]
            finally:
                connection.close()
            if result != "ok":
                raise SystemExit(f"Backup database failed integrity_check: {result}")
            rollback = args.archive.with_name(f"{args.archive.stem}-pre-restore-{time.strftime('%Y%m%d-%H%M%S')}.zip")
            create_backup(rollback)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(candidate_db, db_path)
            for dirname, target in (("uploads", DATA_DIR / "uploads"), ("qdrant", local_qdrant_path())):
                target = target.resolve()
                if target == target.anchor or target == DATA_DIR.resolve():
                    raise SystemExit("Refusing to replace a filesystem root or DATA_DIR")
                if target.exists():
                    shutil.rmtree(target)
                source = temp_root / "data" / dirname
                if source.exists():
                    shutil.copytree(source, target)
            secret = temp_root / "data" / "auth.secret"
            if secret.exists():
                shutil.copy2(secret, DATA_DIR / "auth.secret")
            else:
                (DATA_DIR / "auth.secret").unlink(missing_ok=True)
    print(f"Restore completed. Full pre-restore snapshot: {rollback}")

if __name__ == "__main__":
    main()
