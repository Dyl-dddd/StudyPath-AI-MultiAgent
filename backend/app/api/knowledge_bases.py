import shutil
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.config import DATA_DIR
from app.core.db import get_db
from app.core.security import current_user
from app.models import Document, KnowledgeBase, User
from app.rag.vector_store import delete_knowledge_base as delete_knowledge_base_vectors
from app.schemas import KnowledgeBaseInput

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])


@router.get("")
def list_knowledge_bases(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.execute(select(KnowledgeBase, func.count(Document.id)).outerjoin(Document).where(KnowledgeBase.owner_id == user.id).group_by(KnowledgeBase.id).order_by(KnowledgeBase.created_at.desc())).all()
    return [{"id": kb.id, "name": kb.name, "course_name": kb.course_name, "document_count": count, "created_at": kb.created_at} for kb, count in rows]


@router.get("/{knowledge_base_id}")
def get_knowledge_base(knowledge_base_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    result = db.execute(select(KnowledgeBase, func.count(Document.id)).outerjoin(Document).where(KnowledgeBase.id == knowledge_base_id, KnowledgeBase.owner_id == user.id).group_by(KnowledgeBase.id)).first()
    if not result:
        raise HTTPException(404, "知识库不存在或无权访问")
    kb, count = result
    return {"id": kb.id, "name": kb.name, "course_name": kb.course_name, "document_count": count, "created_at": kb.created_at}


@router.post("", status_code=201)
def create_knowledge_base(payload: KnowledgeBaseInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    kb = KnowledgeBase(id=str(uuid.uuid4()), owner_id=user.id, name=payload.name.strip(), course_name=payload.course_name.strip())
    db.add(kb)
    db.commit()
    return {"id": kb.id, "name": kb.name, "course_name": kb.course_name, "document_count": 0, "created_at": kb.created_at}


@router.patch("/{knowledge_base_id}")
def update_knowledge_base(knowledge_base_id: str, payload: KnowledgeBaseInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    kb = db.scalar(select(KnowledgeBase).where(KnowledgeBase.id == knowledge_base_id, KnowledgeBase.owner_id == user.id))
    if not kb:
        raise HTTPException(404, "知识库不存在")
    kb.name, kb.course_name = payload.name.strip(), payload.course_name.strip()
    db.commit()
    return {"id": kb.id, "name": kb.name, "course_name": kb.course_name}


@router.delete("/{knowledge_base_id}", status_code=204)
def delete_knowledge_base(knowledge_base_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    kb = db.scalar(select(KnowledgeBase).where(KnowledgeBase.id == knowledge_base_id, KnowledgeBase.owner_id == user.id))
    if not kb:
        raise HTTPException(404, "知识库不存在")
    docs = list(db.scalars(select(Document).where(Document.knowledge_base_id == kb.id, Document.owner_id == user.id)).all())
    try:
        delete_knowledge_base_vectors(kb.id, user.id)
    except Exception:
        raise HTTPException(503, "向量索引暂不可用，知识库未删除；请恢复服务后重试") from None
    for doc in docs:
        (DATA_DIR / "uploads" / user.id / doc.storage_name).unlink(missing_ok=True)
    db.delete(kb)
    db.commit()
