import asyncio
import json
import time
import uuid
from typing import Literal
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.db import SessionLocal, get_db
from app.core.security import current_user
from app.models import ChatMessage, ChatSession, Document, DocumentChunk, KnowledgeBase, MessageCitation, MessageFeedback, User, UserCourseBinding
from app.rag.pipeline import answer, retrieve, stream_answer
from app.schemas import ChatInput, FeedbackInput, SessionInput
from app.rag.embeddings import embed_query

router = APIRouter(prefix="/rag", tags=["rag"])


def _session(db: Session, user: User, session_id: str) -> ChatSession:
    session = db.scalar(select(ChatSession).where(ChatSession.id == session_id, ChatSession.owner_id == user.id))
    if not session:
        raise HTTPException(404, "对话不存在或无权访问")
    return session


def _citations_by_message(db: Session, message_ids: list[str]) -> dict[str, list[dict]]:
    if not message_ids:
        return {}
    rows = db.execute(
        select(MessageCitation, Document, DocumentChunk)
        .join(Document, Document.id == MessageCitation.document_id)
        .join(DocumentChunk, DocumentChunk.id == MessageCitation.chunk_id)
        .where(MessageCitation.message_id.in_(message_ids))
        .order_by(MessageCitation.id)
    ).all()
    result: dict[str, list[dict]] = {}
    for citation, document, chunk in rows:
        result.setdefault(citation.message_id, []).append({
            "citation_id": citation.id, "document_id": document.id, "document_name": document.file_name,
            "chunk_id": chunk.id, "page_start": chunk.page_start, "page_end": chunk.page_end,
            "section_title": chunk.section_title, "snippet": chunk.content[:1000],
            "retrieval_score": citation.score,
            "preview_url": f"/documents/{document.id}/preview?chunk_id={chunk.id}",
        })
    return result


@router.post("/sessions", status_code=201)
def create_session(payload: SessionInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    kb = None
    if payload.answer_mode == "library":
        binding = db.scalar(select(UserCourseBinding).where(UserCourseBinding.user_id == user.id, UserCourseBinding.course_id == payload.course_id)) if payload.course_id else None
        knowledge_base_id = binding.knowledge_base_id if binding else payload.knowledge_base_id
        if payload.course_id and binding is None:
            raise HTTPException(404, "该课程尚未绑定个人知识库")
        if payload.knowledge_base_id and binding and payload.knowledge_base_id != binding.knowledge_base_id:
            raise HTTPException(422, "课程绑定的知识库与请求不一致")
        kb = db.scalar(select(KnowledgeBase).where(KnowledgeBase.id == knowledge_base_id, KnowledgeBase.owner_id == user.id))
        if not kb:
            raise HTTPException(404, "知识库不存在")
    session = ChatSession(id=str(uuid.uuid4()), owner_id=user.id, knowledge_base_id=kb.id if kb else None,
                          answer_mode=payload.answer_mode, title=payload.title.strip() or "新建学习对话")
    db.add(session)
    db.commit()
    return {"id": session.id, "knowledge_base_id": session.knowledge_base_id, "answer_mode": session.answer_mode,
            "title": session.title, "created_at": session.created_at}


@router.get("/sessions")
def list_sessions(knowledge_base_id: str | None = None, answer_mode: Literal["library", "model"] | None = None,
                  db: Session = Depends(get_db), user: User = Depends(current_user)):
    query = select(ChatSession).where(ChatSession.owner_id == user.id)
    if knowledge_base_id:
        query = query.where(ChatSession.knowledge_base_id == knowledge_base_id)
    if answer_mode:
        query = query.where(ChatSession.answer_mode == answer_mode)
    return [{"id": item.id, "knowledge_base_id": item.knowledge_base_id, "answer_mode": item.answer_mode,
             "title": item.title, "created_at": item.created_at, "updated_at": item.updated_at}
            for item in db.scalars(query.order_by(ChatSession.updated_at.desc())).all()]


@router.patch("/sessions/{session_id}")
def rename_session(session_id: str, payload: dict, db: Session = Depends(get_db), user: User = Depends(current_user)):
    session = _session(db, user, session_id)
    title = str(payload.get("title", "")).strip()
    if not title or len(title) > 180:
        raise HTTPException(422, "标题长度需为 1–180 个字符")
    session.title = title
    db.commit()
    return {"id": session.id, "title": session.title}


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    session = _session(db, user, session_id)
    db.delete(session)
    db.commit()


@router.get("/sessions/{session_id}/messages")
def list_messages(session_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    session = _session(db, user, session_id)
    messages = list(db.scalars(select(ChatMessage).where(ChatMessage.session_id == session.id).order_by(ChatMessage.created_at)).all())
    citations = _citations_by_message(db, [message.id for message in messages])
    feedback = {row.message_id: row.rating for row in db.scalars(select(MessageFeedback).where(MessageFeedback.user_id == user.id, MessageFeedback.message_id.in_([message.id for message in messages]))).all()} if messages else {}
    return [{"id": message.id, "role": message.role, "content": message.content, "created_at": message.created_at, "citations": citations.get(message.id, []), "feedback": feedback.get(message.id)} for message in messages]


@router.put("/messages/{message_id}/feedback")
def save_message_feedback(message_id: str, payload: FeedbackInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    message = db.scalar(select(ChatMessage).join(ChatSession, ChatSession.id == ChatMessage.session_id).where(
        ChatMessage.id == message_id, ChatMessage.role == "assistant", ChatSession.owner_id == user.id))
    if message is None:
        raise HTTPException(404, "答复不存在或无权评价")
    row = db.scalar(select(MessageFeedback).where(MessageFeedback.user_id == user.id, MessageFeedback.message_id == message.id))
    if row is None:
        row = MessageFeedback(user_id=user.id, message_id=message.id, rating=payload.rating, comment=payload.comment.strip())
        db.add(row)
    else:
        row.rating, row.comment = payload.rating, payload.comment.strip()
    db.commit()
    return {"messageId": message.id, "rating": row.rating, "comment": row.comment}


@router.post("/retrieve")
def debug_retrieve(payload: ChatInput, include_candidates: bool = False, db: Session = Depends(get_db), user: User = Depends(current_user)):
    session = _session(db, user, payload.session_id)
    if session.answer_mode != "library" or not session.knowledge_base_id:
        raise HTTPException(409, "该对话使用大模型问答模式，不执行本地资料检索")
    timings = {}
    started = time.perf_counter()
    candidate_rows: list[dict] = []
    rows, mode = retrieve(db, user, session.knowledge_base_id, payload.question, timings=timings, candidate_sink=candidate_rows if include_candidates else None)
    from app.rag.pipeline import _citations
    timings["total_ms"] = round((time.perf_counter() - started) * 1000, 2)
    response = {"retrieval_mode": mode, "citations": _citations(rows, db, user.id), "timings_ms": timings}
    if include_candidates:
        response["candidates"] = _citations(candidate_rows, db, user.id)
    return response


@router.post("/chat")
async def chat(payload: ChatInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not payload.question.strip():
        raise HTTPException(422, "问题不能为空")
    session = _session(db, user, payload.session_id)
    timings = {}
    request_started = time.perf_counter()
    answer_text, citations, mode = await answer(db, user, session, payload.question.strip(), timings=timings)
    user_message = ChatMessage(id=str(uuid.uuid4()), session_id=session.id, role="user", content=payload.question.strip())
    assistant_message = ChatMessage(id=str(uuid.uuid4()), session_id=session.id, role="assistant", content=answer_text)
    db.add_all([user_message, assistant_message])
    db.flush()
    for citation in citations:
        db.add(MessageCitation(id=str(uuid.uuid4()), message_id=assistant_message.id, document_id=citation["document_id"], chunk_id=citation["chunk_id"], score=citation["retrieval_score"]))
    if session.title == "新建学习对话":
        session.title = payload.question.strip()[:70]
    db.commit()
    timings["total_ms"] = round((time.perf_counter() - request_started) * 1000, 2)
    return {"session_id": session.id, "message_id": assistant_message.id, "answer": answer_text, "citations": citations, "retrieval_mode": mode, "timings_ms": timings}


def _event(name: str, data) -> str:
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False, separators=(',', ':'))}\n\n"


async def _stream(session_id: str, user_id: str, question: str):
    db = SessionLocal()
    full_answer, citation_rows, mode = "", [], "dense"
    try:
        user = db.get(User, user_id)
        session = db.scalar(select(ChatSession).where(ChatSession.id == session_id, ChatSession.owner_id == user_id))
        if not user or not session:
            yield _event("error", {"message": "对话已不存在或无权访问"})
            return
        async for event in stream_answer(db, user, session, question):
            if event["event"] == "citations":
                citation_rows = event["data"]
                yield _event("citations", citation_rows)
            elif event["event"] == "delta":
                full_answer += event["data"]
                yield _event("delta", event["data"])
            elif event["event"] == "done":
                full_answer = event["data"]["answer"]
                mode = event["data"]["retrieval_mode"]
                user_message = ChatMessage(id=str(uuid.uuid4()), session_id=session.id, role="user", content=question)
                assistant_message = ChatMessage(id=str(uuid.uuid4()), session_id=session.id, role="assistant", content=full_answer)
                db.add_all([user_message, assistant_message])
                db.flush()
                for citation in citation_rows:
                    db.add(MessageCitation(id=str(uuid.uuid4()), message_id=assistant_message.id, document_id=citation["document_id"], chunk_id=citation["chunk_id"], score=citation["retrieval_score"]))
                if session.title == "新建学习对话":
                    session.title = question[:70]
                db.commit()
                yield _event("done", {"answer": full_answer, "retrieval_mode": mode, "message_id": assistant_message.id})
            elif event["event"] == "error":
                yield _event("error", event["data"])
    except asyncio.CancelledError:
        db.rollback()
        raise
    except HTTPException as error:
        db.rollback()
        yield _event("error", {"message": error.detail})
    except Exception as error:
        db.rollback()
        yield _event("error", {"message": f"问答失败：{type(error).__name__}"})
    finally:
        db.close()


@router.post("/chat/stream")
def chat_stream(payload: ChatInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not payload.question.strip():
        raise HTTPException(422, "问题不能为空")
    session = _session(db, user, payload.session_id)
    return StreamingResponse(_stream(session.id, user.id, payload.question.strip()), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"})
