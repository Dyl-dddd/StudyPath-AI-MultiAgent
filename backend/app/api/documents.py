import hashlib
import re
import threading
import time
from datetime import datetime, timedelta, timezone
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select, update, delete
from sqlalchemy.orm import Session
from app.core.config import DATA_DIR, get_settings
from app.core.db import SessionLocal, get_db
from app.core.security import current_user
from app.models import Document, DocumentChunk, IndexJob, KnowledgeBase, LearningCourse, KnowledgeEdge, KnowledgeNode, QuizQuestion, User, UserMistake
from app.rag.chunker import chunk_segments
from app.rag.parsers import parse_document
from app.rag.vector_store import delete_chunks, delete_document, upsert_chunks

router = APIRouter(tags=["documents"])
ALLOWED = {"pdf": ("PDF", "application/pdf"), "docx": ("DOCX", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"), "txt": ("TXT", "text/plain"), "md": ("MD", "text/markdown")}
_index_guard = threading.Lock()
_document_locks: dict[str, threading.Lock] = {}


def serialize(doc: Document):
    return {"id": doc.id, "knowledge_base_id": doc.knowledge_base_id, "file_name": doc.file_name, "file_type": doc.file_type, "file_size": doc.file_size, "status": doc.status, "error_message": doc.error_message, "chunk_count": doc.chunk_count, "created_at": doc.created_at}


def _generate_document_learning_assets(db: Session, doc: Document, chunks: list) -> int:
    """Create private graph concepts and one source-grounded question per section."""
    kb = db.get(KnowledgeBase, doc.knowledge_base_id)
    if not kb:
        return 0
    labels = [kb.course_name, kb.name, doc.file_name]
    normalized_labels = [re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", value.lower()) for value in labels if value]
    courses = db.scalars(select(LearningCourse)).all()
    course = next((item for item in courses if re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", item.name.lower()) in normalized_labels), None)
    if course is None:
        course = next((item for item in sorted(courses, key=lambda row: len(row.name), reverse=True)
                       if len(item.name) >= 3 and any(item.name in value or value in item.name for value in labels if value)), None)
    if course is None:
        return 0

    grouped: dict[str, list[str]] = {}
    for chunk in chunks:
        text = (chunk.content or "").strip()
        if not text:
            continue
        title = (chunk.section_title or "").strip()
        if not title or title.lower() in {"正文", "内容", "未分类", "document"}:
            title = re.split(r"[。！？.!?\n]", text, maxsplit=1)[0].strip()[:40] or f"资料片段 {len(grouped) + 1}"
        if title not in grouped and len(grouped) >= 40:
            continue
        grouped.setdefault(title[:180], []).append(text)
    sections = [(title, "\n".join(parts)) for title, parts in grouped.items()]
    if not sections:
        return 0

    # Re-indexing replaces this document's generated assets without affecting other uploads.
    old_question_ids = db.scalars(select(QuizQuestion.id).where(QuizQuestion.source_document_id == doc.id, QuizQuestion.owner_id == doc.owner_id)).all()
    if old_question_ids:
        db.execute(delete(UserMistake).where(UserMistake.user_id == doc.owner_id, UserMistake.question_id.in_(old_question_ids)))
    db.execute(delete(QuizQuestion).where(QuizQuestion.source_document_id == doc.id, QuizQuestion.owner_id == doc.owner_id))
    db.execute(delete(KnowledgeEdge).where(KnowledgeEdge.source_document_id == doc.id, KnowledgeEdge.owner_id == doc.owner_id))
    db.execute(delete(KnowledgeNode).where(KnowledgeNode.source_document_id == doc.id, KnowledgeNode.owner_id == doc.owner_id))
    db.flush()

    descriptions: list[str] = []
    for _title, text in sections:
        sentence = re.split(r"(?<=[。！？.!?])\s*|\n+", text.strip(), maxsplit=1)[0].strip()
        descriptions.append((sentence or text).replace("\x00", "")[:700])
    created = 0
    for index, ((title, _text), description) in enumerate(zip(sections, descriptions)):
        node_id = f"doc-{doc.id.replace('-', '')[:24]}-{index + 1}"
        node = KnowledgeNode(id=node_id, course_id=course.id, name=title, type="concept", description=description,
                             owner_id=doc.owner_id, source_document_id=doc.id)
        db.add(node)
        db.flush()
        db.add(KnowledgeEdge(course_id=course.id, source=course.id, target=node.id,
                             owner_id=doc.owner_id, source_document_id=doc.id))
        options = [description]
        for distractor in descriptions:
            if distractor != description and distractor not in options:
                options.append(distractor)
            if len(options) >= 4:
                break
        while len(options) < 4:
            options.append(f"资料未将第 {len(options) + 1} 项内容作为该主题的核心表述。")
        db.add(QuizQuestion(course_id=course.id, owner_id=doc.owner_id, source_document_id=doc.id,
                            type="单选题", difficulty="基础", topic=title, concept_id=node.id,
                            title=f"根据《{doc.file_name}》，关于“{title}”的核心表述是哪一项？",
                            options=options, answer=description, explanation=description,
                            evidence={"title": doc.file_name, "section": title, "excerpt": description}))
        created += 1
    return created


def backfill_ready_document_learning_assets(db: Session) -> int:
    """Generate assets for already indexed uploads that predate this feature."""
    documents = db.scalars(select(Document).where(Document.status == "READY").order_by(Document.created_at)).all()
    generated = 0
    for doc in documents:
        existing = db.scalar(select(KnowledgeNode.id).where(
            KnowledgeNode.source_document_id == doc.id,
            KnowledgeNode.owner_id == doc.owner_id,
        ).limit(1))
        if existing:
            continue
        chunks = db.scalars(select(DocumentChunk).where(
            DocumentChunk.document_id == doc.id,
            DocumentChunk.owner_id == doc.owner_id,
        ).order_by(DocumentChunk.chunk_index)).all()
        generated += _generate_document_learning_assets(db, doc, chunks)
    db.commit()
    return generated


def index_document(document_id: str):
    with _index_guard:
        lock = _document_locks.setdefault(document_id, threading.Lock())
    with lock:
        _index_document_unlocked(document_id)


def _index_document_unlocked(document_id: str):
    db = SessionLocal()
    try:
        doc = db.get(Document, document_id)
        if not doc:
            return
        if doc.status != "UPLOADED":
            return
        source = DATA_DIR / "uploads" / doc.owner_id / doc.storage_name
        doc.status, doc.error_message = "PARSING", ""
        db.commit()
        segments = parse_document(source, doc.file_type)
        doc.extracted_text = "\n\n".join(segment.text for segment in segments)
        if not segments:
            if doc.file_type == "PDF":
                raise ValueError("PDF 未提取到可搜索文字；可能是扫描件，需要 OCR 处理")
            raise ValueError("文档没有可索引的文字内容")
        doc.status = "CHUNKING"
        db.commit()
        chunks = chunk_segments(segments, document_id=doc.id, file_hash=doc.file_hash)
        if not chunks:
            raise ValueError("没有生成有效文本分块")
        doc.status = "EMBEDDING"
        db.commit()
        from app.core.config import get_settings
        payloads = [{"chunk_id": chunk.id, "document_id": doc.id, "knowledge_base_id": doc.knowledge_base_id, "owner_id": doc.owner_id, "content": chunk.content, "page_start": chunk.page_start, "page_end": chunk.page_end, "section_title": chunk.section_title, "chunk_index": chunk.chunk_index, "token_count": chunk.token_count, "content_hash": chunk.content_hash, "document_name": doc.file_name} for chunk in chunks]
        upsert_chunks(payloads)
        doc.status = "INDEXING"
        db.commit()
        old = list(db.scalars(select(DocumentChunk).where(DocumentChunk.document_id == doc.id)).all())
        wanted = {chunk.id for chunk in chunks}
        stale = [chunk.id for chunk in old if chunk.id not in wanted]
        if stale:
            delete_chunks(stale)
        for chunk in old:
            db.delete(chunk)
        from app.rag.embeddings import model
        for chunk in chunks:
            db.add(DocumentChunk(id=chunk.id, document_id=doc.id, knowledge_base_id=doc.knowledge_base_id, owner_id=doc.owner_id, content=chunk.content, page_start=chunk.page_start, page_end=chunk.page_end, section_title=chunk.section_title, chunk_index=chunk.chunk_index, token_count=chunk.token_count, content_hash=chunk.content_hash, model_version=get_settings().embedding_model))
        doc.chunk_count, doc.status, doc.error_message = len(chunks), "READY", ""
        _generate_document_learning_assets(db, doc, chunks)
        db.commit()
    except Exception as error:
        db.rollback()
        doc = db.get(Document, document_id)
        if doc:
            try:
                delete_document(doc.id, doc.owner_id)
            except Exception:
                pass
            doc.status, doc.error_message = "FAILED", f"{type(error).__name__}: {str(error)[:400]}"
            db.commit()
    finally:
        db.close()


_worker_stop = threading.Event()
_worker_thread: threading.Thread | None = None


def _claim_job() -> str | None:
    db = SessionLocal()
    try:
        job = db.scalar(select(IndexJob).where(IndexJob.status == "PENDING").order_by(IndexJob.created_at).limit(1))
        if not job:
            return None
        claimed = db.execute(update(IndexJob).where(IndexJob.id == job.id, IndexJob.status == "PENDING").values(status="RUNNING", attempts=IndexJob.attempts + 1, updated_at=datetime.now(timezone.utc)))
        db.commit()
        return job.id if claimed.rowcount else None
    except Exception:
        db.rollback()
        return None
    finally:
        db.close()


def _process_job(job_id: str) -> None:
    db = SessionLocal()
    try:
        job = db.get(IndexJob, job_id)
        if not job or job.status != "RUNNING":
            return
        document_id = job.document_id
    finally:
        db.close()
    index_document(document_id)
    db = SessionLocal()
    try:
        job = db.get(IndexJob, job_id)
        doc = db.get(Document, document_id)
        if job:
            job.status = "DONE" if doc and doc.status == "READY" else "FAILED"
            job.updated_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()


def start_index_worker() -> None:
    global _worker_thread
    _worker_stop.clear()
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        expired = list(db.scalars(select(IndexJob).where(IndexJob.status == "RUNNING", IndexJob.updated_at < cutoff)).all())
        for job in expired:
            doc = db.get(Document, job.document_id)
            if doc and doc.status != "READY":
                doc.status, doc.error_message = "UPLOADED", ""
            job.status, job.updated_at = "PENDING", datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()

    def run():
        while not _worker_stop.is_set():
            job_id = _claim_job()
            if job_id:
                _process_job(job_id)
            else:
                _worker_stop.wait(1.0)

    _worker_thread = threading.Thread(target=run, name="studypath-index-worker", daemon=True)
    _worker_thread.start()


def stop_index_worker() -> None:
    _worker_stop.set()
    if _worker_thread and _worker_thread.is_alive():
        _worker_thread.join(timeout=10)


@router.post("/knowledge-bases/{knowledge_base_id}/documents", status_code=202)
async def upload_document(knowledge_base_id: str, file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(current_user)):
    kb = db.scalar(select(KnowledgeBase).where(KnowledgeBase.id == knowledge_base_id, KnowledgeBase.owner_id == user.id))
    if not kb:
        raise HTTPException(404, "知识库不存在或无权访问")
    original_name = re.split(r"[\\/]", file.filename or "")[-1].strip().replace("\x00", "").replace("\r", "").replace("\n", "")
    ext = Path(original_name).suffix.lower().lstrip(".")
    if ext not in ALLOWED:
        raise HTTPException(415, "仅支持 PDF、DOCX、TXT、Markdown")
    mime = (file.content_type or "").split(";")[0].lower()
    accepted_mime = {ALLOWED[ext][1], "application/octet-stream"}
    if ext == "pdf": accepted_mime.add("application/x-pdf")
    if ext == "md": accepted_mime.add("text/plain")
    if mime and mime not in accepted_mime:
        raise HTTPException(415, "文件 MIME 类型与扩展名不匹配")
    limit = get_settings().max_upload_mb * 1024 * 1024
    raw = await file.read(limit + 1)
    if len(raw) > limit:
        raise HTTPException(413, f"文件不能超过 {get_settings().max_upload_mb} MB")
    if not raw:
        raise HTTPException(400, "文件为空")
    if ext == "pdf" and not raw.startswith(b"%PDF-"):
        raise HTTPException(415, "文件内容与 PDF 扩展名不匹配")
    if ext == "docx" and not raw.startswith(b"PK\x03\x04"):
        raise HTTPException(415, "文件内容与 DOCX 扩展名不匹配")
    if ext in ("txt", "md") and b"\x00" in raw:
        raise HTTPException(415, "文本文件包含二进制内容")
    digest = hashlib.sha256(raw).hexdigest()
    if db.scalar(select(Document).where(Document.owner_id == user.id, Document.knowledge_base_id == kb.id, Document.file_hash == digest)):
        raise HTTPException(409, "该知识库已上传相同文件")
    doc_id = str(uuid.uuid4())
    storage_name = f"{doc_id}.{ext}"
    directory = DATA_DIR / "uploads" / user.id
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / storage_name
    destination.write_bytes(raw)
    doc = Document(id=doc_id, owner_id=user.id, knowledge_base_id=kb.id, file_name=original_name[:255], storage_name=storage_name, file_type=ALLOWED[ext][0], file_size=len(raw), file_hash=digest, status="UPLOADED")
    db.add(doc)
    db.flush()
    db.add(IndexJob(id=str(uuid.uuid4()), document_id=doc.id, status="PENDING"))
    db.commit()
    return serialize(doc)


@router.get("/knowledge-bases/{knowledge_base_id}/documents")
def list_documents(knowledge_base_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    kb = db.scalar(select(KnowledgeBase).where(KnowledgeBase.id == knowledge_base_id, KnowledgeBase.owner_id == user.id))
    if not kb:
        raise HTTPException(404, "知识库不存在")
    return [serialize(item) for item in db.scalars(select(Document).where(Document.knowledge_base_id == kb.id, Document.owner_id == user.id).order_by(Document.created_at.desc())).all()]


@router.get("/documents/{document_id}/status")
def document_status(document_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    doc = db.scalar(select(Document).where(Document.id == document_id, Document.owner_id == user.id))
    if not doc:
        raise HTTPException(404, "文档不存在")
    return serialize(doc)


@router.post("/documents/{document_id}/reindex", status_code=202)
def reindex_document(document_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    doc = db.scalar(select(Document).where(Document.id == document_id, Document.owner_id == user.id))
    if not doc:
        raise HTTPException(404, "文档不存在")
    if doc.status in {"PARSING", "CHUNKING", "EMBEDDING", "INDEXING"}:
        raise HTTPException(409, "文档正在处理中")
    doc.status, doc.error_message = "UPLOADED", ""
    db.add(IndexJob(id=str(uuid.uuid4()), document_id=doc.id, status="PENDING"))
    db.commit()
    return serialize(doc)


@router.delete("/documents/{document_id}", status_code=204)
def delete_doc(document_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    doc = db.scalar(select(Document).where(Document.id == document_id, Document.owner_id == user.id))
    if not doc:
        raise HTTPException(404, "文档不存在")
    try:
        delete_document(doc.id, user.id)
    except Exception:
        raise HTTPException(503, "向量索引暂不可用，文档未删除；请恢复服务后重试") from None
    (DATA_DIR / "uploads" / user.id / doc.storage_name).unlink(missing_ok=True)
    question_ids = db.scalars(select(QuizQuestion.id).where(QuizQuestion.source_document_id == doc.id, QuizQuestion.owner_id == user.id)).all()
    if question_ids:
        db.execute(delete(UserMistake).where(UserMistake.user_id == user.id, UserMistake.question_id.in_(question_ids)))
        db.execute(delete(QuizQuestion).where(QuizQuestion.id.in_(question_ids), QuizQuestion.owner_id == user.id))
    db.execute(delete(KnowledgeEdge).where(KnowledgeEdge.source_document_id == doc.id, KnowledgeEdge.owner_id == user.id))
    db.execute(delete(KnowledgeNode).where(KnowledgeNode.source_document_id == doc.id, KnowledgeNode.owner_id == user.id))
    db.delete(doc)
    db.commit()


@router.get("/documents/{document_id}/preview")
def preview_document(document_id: str, chunk_id: str | None = None, page: int | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)):
    doc = db.scalar(select(Document).where(Document.id == document_id, Document.owner_id == user.id))
    if not doc:
        raise HTTPException(404, "文档不存在")
    if chunk_id:
        chunk = db.scalar(select(DocumentChunk).where(DocumentChunk.id == chunk_id, DocumentChunk.document_id == doc.id, DocumentChunk.owner_id == user.id))
        if not chunk:
            raise HTTPException(404, "原文片段不存在")
        original_text = chunk.content
        if doc.file_type == "PDF" and chunk.page_start:
            import pymupdf
            with pymupdf.open(DATA_DIR / "uploads" / user.id / doc.storage_name) as pdf:
                if 1 <= chunk.page_start <= pdf.page_count:
                    original_text = pdf[chunk.page_start - 1].get_text("text")
        return {"document_id": doc.id, "document_name": doc.file_name, "page": chunk.page_start, "page_end": chunk.page_end, "section_title": chunk.section_title, "text": original_text, "highlight": chunk.content}
    if doc.file_type == "PDF":
        import fitz
        with fitz.open(DATA_DIR / "uploads" / user.id / doc.storage_name) as pdf:
            page_num = max(1, min(page or 1, pdf.page_count))
            text = pdf[page_num - 1].get_text("text")
        return {"document_id": doc.id, "document_name": doc.file_name, "page": page_num, "text": text, "highlight": ""}
    return {"document_id": doc.id, "document_name": doc.file_name, "page": None, "text": doc.extracted_text[:16000], "highlight": ""}


@router.get("/documents/{document_id}/file")
def download_document(document_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    doc = db.scalar(select(Document).where(Document.id == document_id, Document.owner_id == user.id))
    if not doc:
        raise HTTPException(404, "文档不存在")
    return FileResponse(DATA_DIR / "uploads" / user.id / doc.storage_name, filename=doc.file_name)
