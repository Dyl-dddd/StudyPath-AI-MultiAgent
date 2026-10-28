import json
from contextlib import asynccontextmanager
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.api import documents as documents_api
from app.api import rag as rag_api
from app.api import auth as auth_api
from app.core.db import Base, get_db
from app.main import app
from app.models import Document, DocumentChunk


@asynccontextmanager
async def _test_lifespan(_app):
    yield


def test_student_can_upload_index_chat_stream_and_delete_isolated_course_material(tmp_path, monkeypatch):
    database = tmp_path / "acceptance.sqlite"
    engine = create_engine(f"sqlite:///{database.as_posix()}", connect_args={"check_same_thread": False})
    sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)

    def override_db():
        db = sessions()
        try:
            yield db
        finally:
            db.close()

    data_dir = tmp_path / "data"
    monkeypatch.setattr(documents_api, "DATA_DIR", data_dir)
    monkeypatch.setattr(documents_api, "SessionLocal", sessions)
    monkeypatch.setattr(rag_api, "SessionLocal", sessions)
    monkeypatch.setattr(documents_api, "upsert_chunks", lambda _chunks: None)
    monkeypatch.setattr(documents_api, "delete_document", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(auth_api, "_consume_registration_captcha", lambda *_args: None)
    monkeypatch.setattr(app.router, "lifespan_context", _test_lifespan)
    app.dependency_overrides[get_db] = override_db

    answer_text = "进程是运行中的程序实例。[1] 不应出现的引用[99]。"

    async def completion_create(*, stream=False, **_kwargs):
        if not stream:
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=answer_text))])

        async def events():
            for part in ("进程是运行中的程序实例。[1] 不应出现的引用[", "99]。"):
                yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=part))])

        return events()

    completion = SimpleNamespace(create=completion_create)
    from app.rag import pipeline
    monkeypatch.setattr(pipeline, "_client", lambda: SimpleNamespace(chat=SimpleNamespace(completions=completion)))
    monkeypatch.setattr(pipeline, "embed_query", lambda _question: [0.1, 0.2])

    def candidate_search(*_args, **_kwargs):
        with sessions() as db:
            chunks = db.scalars(select(DocumentChunk)).all()
            return [
                {"chunk_id": chunk.id, "document_id": chunk.document_id, "owner_id": chunk.owner_id,
                 "knowledge_base_id": chunk.knowledge_base_id, "content": chunk.content,
                 "page_start": chunk.page_start, "page_end": chunk.page_end,
                 "section_title": chunk.section_title, "document_name": db.get(Document, chunk.document_id).file_name,
                 "score": 0.75}
                for chunk in chunks
            ]

    monkeypatch.setattr(pipeline, "search", candidate_search)
    monkeypatch.setattr(pipeline, "rerank", lambda _question, candidates: ([{**item, "score": 0.91} for item in candidates], "dense+rerank"))

    try:
        with TestClient(app) as client:
            registered = client.post("/api/auth/register", json={"username": "acceptance_student", "password": "long-acceptance-password", "password_confirm": "long-acceptance-password", "captcha_id": "00000000-0000-0000-0000-000000000000", "captcha_code": "ABCDE"})
            assert registered.status_code == 201
            headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}

            created_kb = client.post("/api/knowledge-bases", headers=headers, json={"name": "系统验收课程", "course_name": "操作系统"})
            assert created_kb.status_code == 201
            kb_id = created_kb.json()["id"]

            uploaded = client.post(
                f"/api/knowledge-bases/{kb_id}/documents", headers=headers,
                files={"file": ("process.md", "# 进程管理\n\n进程是运行中的程序实例。进程拥有独立的地址空间。", "text/markdown")},
            )
            assert uploaded.status_code == 202
            document_id = uploaded.json()["id"]

            job_id = documents_api._claim_job()
            assert job_id is not None
            documents_api._process_job(job_id)
            indexed = client.get(f"/api/documents/{document_id}/status", headers=headers)
            assert indexed.status_code == 200
            assert indexed.json()["status"] == "READY"
            assert indexed.json()["chunk_count"] > 0

            created_session = client.post("/api/rag/sessions", headers=headers, json={"knowledge_base_id": kb_id})
            assert created_session.status_code == 201
            session_id = created_session.json()["id"]

            chat = client.post("/api/rag/chat", headers=headers, json={"session_id": session_id, "question": "什么是进程？"})
            assert chat.status_code == 200
            assert "[1]" in chat.json()["answer"]
            assert "[99]" not in chat.json()["answer"]
            assert len(chat.json()["citations"]) == 1
            assert client.get(f"/api/rag/sessions/{session_id}/messages", headers=headers).json()[-1]["citations"]
            assert client.get("/api/rag/sessions", headers=headers).json()[0]["title"] == "什么是进程？"

            stream_session = client.post("/api/rag/sessions", headers=headers, json={"knowledge_base_id": kb_id}).json()
            with client.stream("POST", "/api/rag/chat/stream", headers=headers, json={"session_id": stream_session["id"], "question": "进程是什么？"}) as response:
                assert response.status_code == 200
                stream_body = "".join(response.iter_text())
            assert "event: citations" in stream_body
            assert "event: done" in stream_body
            done_data = next(line.removeprefix("data: ") for line in stream_body.splitlines() if line.startswith("data: ") and '"answer"' in line)
            final = json.loads(done_data)
            assert "[99]" not in final["answer"]
            assert client.get("/api/rag/sessions", headers=headers).json()[0]["title"] == "进程是什么？"

            deleted = client.delete(f"/api/documents/{document_id}", headers=headers)
            assert deleted.status_code == 204
            assert client.get(f"/api/documents/{document_id}/status", headers=headers).status_code == 404
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
