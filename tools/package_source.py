"""Create a source-only archive for the StudyPath AI project."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "智学研途AI平台_源代码.zip"
INCLUDE = (
    "src",
    "public",
    "backend/app",
    "backend/migrations",
    "backend/scripts",
    "backend/tests",
    "backend/examples",
    "README.md",
    "package.json",
    "package-lock.json",
    "index.html",
    "tsconfig.json",
    "tsconfig.app.json",
    "vite.config.ts",
    ".gitignore",
    ".env.example",
    "backend/requirements.txt",
    "backend/alembic.ini",
    "backend/.env.example",
    "backend/LEARNING_API.md",
    "backend/OPERATIONS.md",
    "docs/copyright/build_docx_drafts.py",
    "docs/copyright/build_source_excerpt.py",
    "docs/copyright/demo_materials",
    "tools/package_source.py",
)
EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    "dist",
    "data",
}


def is_excluded(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if any(part in EXCLUDED_PARTS for part in relative.parts):
        return True
    if path.name == ".env" or path.name.startswith("~$"):
        return True
    if relative.parts[:3] == ("docs", "copyright", "screenshots"):
        return True
    if relative.parts[:2] == ("docs", "copyright") and path.suffix.lower() in {".pdf", ".docx"}:
        return True
    return False


def main() -> None:
    files: set[Path] = set()
    for item in INCLUDE:
        path = ROOT / item
        if not path.exists():
            continue
        if path.is_file():
            candidates = (path,)
        else:
            candidates = path.rglob("*")
        files.update(candidate for candidate in candidates if candidate.is_file() and not is_excluded(candidate))

    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(ARCHIVE, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(files):
            archive.write(path, path.relative_to(ROOT).as_posix())

    print(f"Created {ARCHIVE}")
    print(f"Files: {len(files)}")
    print(f"Size: {ARCHIVE.stat().st_size / (1024 * 1024):.2f} MiB")


if __name__ == "__main__":
    main()
