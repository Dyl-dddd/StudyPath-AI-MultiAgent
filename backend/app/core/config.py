from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore")
    database_url: str = "sqlite:///./data/studypath.db"
    data_root: str = ""
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_local_path: str = ""
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    fastembed_cache_path: str = ""
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    agentharness_api: str = ""
    jwt_secret: str = ""
    content_admin_token: str = ""
    content_admin_usernames: str = ""
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    max_upload_mb: int = 20
    login_ip_limit: int = 30
    login_user_ip_limit: int = 10
    register_ip_limit: int = 10
    captcha_ip_limit: int = 60
    auth_rate_window_seconds: int = 900
    index_worker_enabled: bool = True
    ocr_enabled: bool = False
    ocr_languages: str = "chi_sim+eng"
    ocr_max_pages: int = 30
    ocr_dpi: int = 180
    tesseract_cmd: str = ""
    tessdata_dir: str = ""
    reranker_concurrency: int = 8
    retrieval_candidates: int = 16
    final_evidence_count: int = 5
    # Calibrated on the local course answerable set (minimum retained positive: 0.7803)
    # and checked against its separate no-answer holdout. Deployments with another
    # reranker/corpus must re-calibrate this floor before changing the model.
    min_evidence_score: float | None = 0.78
    max_evidence_per_document: int = 3
    max_evidence_per_section: int = 2
    reranker_model: str = ""
    reranker_min_score: float | None = None
    collection_name: str = "studypath_chunks"

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


_configured_data_root = get_settings().data_root.strip()
if _configured_data_root:
    _data_root_path = Path(_configured_data_root)
    DATA_DIR = _data_root_path if _data_root_path.is_absolute() else (BACKEND_DIR / _data_root_path).resolve()
else:
    DATA_DIR = BACKEND_DIR / "data"
