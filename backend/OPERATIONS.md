# StudyPath backend operations

## Schema migrations

The API applies Alembic migrations during startup. Existing complete databases are stamped at `0001_legacy_schema` and then upgraded; incomplete legacy schemas stop startup for inspection. Before deploying to production, take a backup and run `alembic upgrade head` from `backend/` against a staging copy first. Set `DATABASE_URL` to PostgreSQL for multi-instance deployments.

## Login and registration throttling

SQLite and PostgreSQL use a shared database counter, so limits apply across API processes. Defaults are 30 login attempts per IP and 10 per username/IP pair in a 15 minute window, plus 10 registrations per IP per window. Configure `LOGIN_IP_LIMIT`, `LOGIN_USER_IP_LIMIT`, `REGISTER_IP_LIMIT`, and `AUTH_RATE_WINDOW_SECONDS`. The application trusts the direct socket address and ignores forwarded headers; configure a trusted reverse proxy that passes the client address through an app-level trusted-proxy solution before relying on IP limits behind a proxy.

## Persistent document indexing

Uploads and reindex requests write `index_jobs` in the same transaction as document state. The lifespan worker claims pending jobs from the database and resumes expired running jobs on startup. For horizontal scaling, use PostgreSQL and remote Qdrant, run one API process with `INDEX_WORKER_ENABLED=true`, and set `INDEX_WORKER_ENABLED=false` on the other API replicas. Do not run multiple worker-enabled replicas against local embedded Qdrant.

## Local backup and restore

Stop every API and indexing worker before backing up local embedded Qdrant. From `backend/`:

`DATA_ROOT` can point the application at a dedicated runtime data directory; the default remains `backend/data`. Use this to keep deployments and isolated restore drills separate from the source tree.

```powershell
.venv\Scripts\python.exe -m scripts.backup_data D:\backups\studypath.zip --service-stopped
.venv\Scripts\python.exe -m scripts.restore_data D:\backups\studypath.zip --service-stopped --confirm-restore
```

The archive contains the SQLite database, uploads, local Qdrant files, and optional auth secret. Store it outside the application data directory and restrict access because uploads may contain private course material. Restore creates a full pre-restore snapshot beside the supplied archive before replacing local runtime data. Test restore on a separate staging copy before using a backup for disaster recovery.

For PostgreSQL, use `pg_dump --format=custom --file=studypath.dump "$env:DATABASE_URL"` and restore with `pg_restore --clean --if-exists --dbname "$env:DATABASE_URL" studypath.dump`; back up remote Qdrant through its snapshot API and uploads through the storage provider's versioned backup. Keep database, vector snapshots, and uploads from a coordinated point in time.

## OCR for scans and embedded DOCX images

Install the Tesseract executable and the `chi_sim` and `eng` language data on the host. `TESSDATA_DIR` points to the folder containing the requested `.traineddata` files, which is useful when the service account cannot write into the system Tesseract installation directory. Install Python dependencies from `requirements.txt`, then configure:

```dotenv
OCR_ENABLED=true
OCR_LANGUAGES=chi_sim+eng
OCR_MAX_PAGES=30
OCR_DPI=180
TESSERACT_CMD="C:\Program Files\Tesseract-OCR\tesseract.exe"
TESSDATA_DIR="D:/StudyPathAI/tessdata"
```

OCR runs for PDF pages with no or very little extractable text and for embedded DOCX images. On Windows, use an ASCII-only `TESSDATA_DIR`; some Tesseract builds fail when the trained-data path contains non-ASCII characters. The directory must contain the selected `.traineddata` files. OCR is bounded by page/image count and Tesseract timeout. Validate OCR output on representative course scans before production use; formulas and complex tables may still need manual correction.

## Evidence score floor

`MIN_EVIDENCE_SCORE` defaults to `0.78`, a conservative local floor selected from the answerable calibration questions (the lowest retained positive score was `0.7803`) and checked against the separate no-answer holdout. This reduced the known off-topic evidence case from a passing top score of `-0.22` to deterministic abstention while preserving the existing 33/34 answerable evidence-retention result. Treat it as a local baseline only: re-calibrate when the reranker, embedding model or corpus changes. For a new corpus, `scripts/evaluate_rag.py` writes candidates to `evaluation/results/retrieval-relevance-review.csv`; reviewers should fill `relevant` with `1` for useful evidence and `0` otherwise, then run `python scripts/calibrate_evidence_floor.py ...`. Section-match proxy metrics are not a substitute for semantic relevance labels.
