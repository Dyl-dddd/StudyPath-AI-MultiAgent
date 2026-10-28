"""Create a service-stopped archive of local StudyPath runtime data."""
import argparse
import zipfile
from pathlib import Path
from sqlalchemy.engine import make_url
from app.core.config import BACKEND_DIR, DATA_DIR, get_settings

ALLOWED_FILES = ("auth.secret",)

def local_qdrant_path() -> Path:
    configured = get_settings().qdrant_local_path.strip()
    path = Path(configured) if configured else DATA_DIR / "qdrant"
    return path if path.is_absolute() else (DATA_DIR.parent / path).resolve()

def database_file() -> Path | None:
    url = get_settings().database_url
    if not url.startswith("sqlite:"):
        return None
    raw = make_url(url).database
    if not raw:
        return None
    path = Path(raw)
    if path.is_absolute() or (len(raw) >= 3 and raw[1:3] in (":\\", ":/")):
        return path
    return (BACKEND_DIR / path).resolve()

def create_backup(destination: Path) -> None:
    if not get_settings().database_url.startswith("sqlite:"):
        raise SystemExit("Remote PostgreSQL: use pg_dump/pg_restore as documented in OPERATIONS.md")
    if get_settings().qdrant_url:
        raise SystemExit("Remote Qdrant needs its own snapshot; this script only backs up local Qdrant")
    db_path = database_file()
    if not db_path or not db_path.is_file():
        raise SystemExit(f"SQLite database not found: {db_path}")
    destination = destination.resolve()
    if destination.is_relative_to(DATA_DIR.resolve()):
        raise SystemExit("Write backups outside backend/data to avoid including the archive in runtime data")
    destination.parent.mkdir(parents=True, exist_ok=True)
    members = [db_path]
    if (DATA_DIR / "uploads").exists():
        members.append(DATA_DIR / "uploads")
    if not get_settings().qdrant_url and local_qdrant_path().exists():
        members.append(local_qdrant_path())
    members += [DATA_DIR / name for name in ALLOWED_FILES if (DATA_DIR / name).is_file()]
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in members:
            arc_root = Path("database") if path == db_path else Path("data")
            if path == db_path:
                archive.write(path, arc_root / "studypath.db")
            elif path.is_dir():
                for child in path.rglob("*"):
                    if child.is_file() and not child.is_symlink():
                        archive.write(child, arc_root / ("qdrant" if path == local_qdrant_path() else path.name) / child.relative_to(path))
            else:
                archive.write(path, arc_root / path.name)
    print(f"Backup created: {destination.resolve()} ({destination.stat().st_size} bytes)")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--service-stopped", action="store_true", help="confirm API and workers are stopped")
    args = parser.parse_args()
    if not args.service_stopped:
        raise SystemExit("Stop all StudyPath API/worker processes, then pass --service-stopped")
    create_backup(args.destination)

if __name__ == "__main__":
    main()
