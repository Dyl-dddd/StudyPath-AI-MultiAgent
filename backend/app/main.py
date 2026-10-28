import logging
from contextlib import asynccontextmanager
import secrets
from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from app.api import agents, auth, content_admin, documents, knowledge_bases, learning, learning_extended, rag
from app.core.config import DATA_DIR, get_settings
from app.core.db import get_db, SessionLocal
from app.core.security import current_user
from app.models import KnowledgeEdge, KnowledgeNode, QuizQuestion, User, UserMistake
from app.api.learning import seed_learning_catalog
from app.api.documents import backfill_ready_document_learning_assets, start_index_worker, stop_index_worker
from app.core.migrations import upgrade_database
from app.rag.vector_store import delete_owner

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("studypath")


@asynccontextmanager
async def lifespan(_app):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "uploads").mkdir(parents=True, exist_ok=True)
    upgrade_database()
    with SessionLocal() as db:
        seed_learning_catalog(db)
        generated_assets = backfill_ready_document_learning_assets(db)
        if generated_assets:
            logger.info("Generated learning assets for existing indexed documents: %s", generated_assets)
    if get_settings().index_worker_enabled:
        start_index_worker()
    yield
    if get_settings().index_worker_enabled:
        stop_index_worker()


app = FastAPI(title="StudyPath AI RAG API", version="1.0.0", description="Document-grounded learning assistant API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().allowed_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(auth.router, prefix="/api")
app.include_router(knowledge_bases.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(rag.router, prefix="/api")
app.include_router(agents.router, prefix="/api")
app.include_router(learning.router, prefix="/api")
app.include_router(learning_extended.router)
app.include_router(content_admin.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "llm_configured": bool(get_settings().llm_base_url and get_settings().llm_api_key and get_settings().llm_model), "reranker_configured": bool(get_settings().reranker_model), "reranker_gate_enabled": get_settings().reranker_min_score is not None, "reranker_min_score": get_settings().reranker_min_score, "embedding_model": get_settings().embedding_model, "vector_store": "remote" if get_settings().qdrant_url else "local-persistent"}


@app.delete("/api/auth/me", status_code=204)
def delete_account(db: Session = Depends(get_db), user: User = Depends(current_user)):
    try:
        delete_owner(user.id)
    except Exception:
        raise HTTPException(503, "向量索引不可用，账户数据未删除；请恢复服务后重试") from None
    directory = DATA_DIR / "uploads" / user.id
    upload_root = (DATA_DIR / "uploads").resolve()
    if directory.exists() and directory.resolve().parent == upload_root:
        import shutil
        shutil.rmtree(directory)
    generated_question_ids = select(QuizQuestion.id).where(QuizQuestion.owner_id == user.id)
    db.execute(delete(UserMistake).where(UserMistake.user_id == user.id, UserMistake.question_id.in_(generated_question_ids)))
    db.execute(delete(QuizQuestion).where(QuizQuestion.owner_id == user.id))
    db.execute(delete(KnowledgeEdge).where(KnowledgeEdge.owner_id == user.id))
    db.execute(delete(KnowledgeNode).where(KnowledgeNode.owner_id == user.id))
    db.delete(user)
    db.commit()
