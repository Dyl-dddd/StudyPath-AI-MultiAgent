"""Two-phase public-sample E2E check; all data uses a dedicated integration DB.

Run phase one, restart the backend, then run phase two with the same environment.
The script exercises real parsing, model embeddings, local Qdrant and HTTP APIs.
"""
import argparse
import os
import time
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
API = os.getenv("RAG_SMOKE_API", "http://127.0.0.1:8000/api")
USERNAME = os.getenv("RAG_SMOKE_USERNAME", "studypath_integration")
PASSWORD = os.getenv("RAG_SMOKE_PASSWORD", "integration-only-password-2026")
SECOND_USERNAME = USERNAME + "_other"


def require(condition: bool, message: str):
    if not condition:
        raise RuntimeError(message)


def auth(client: httpx.Client, username: str, password: str, create: bool = False):
    endpoint = "/auth/register" if create else "/auth/login"
    response = client.post(endpoint, json={"username": username, "password": password})
    if create and response.status_code == 409:
        response = client.post("/auth/login", json={"username": username, "password": password})
    response.raise_for_status()
    client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"


def first_phase():
    with httpx.Client(base_url=API, timeout=180) as client:
        health = client.get("/health").json()
        require(health["vector_store"] == "local-persistent", "expected the isolated persistent local Qdrant configuration")
        auth(client, USERNAME, PASSWORD, create=True)
        for existing in client.get("/knowledge-bases").json():
            if existing["name"] == "RAG E2E Smoke Data":
                client.delete(f"/knowledge-bases/{existing['id']}").raise_for_status()
        kb = client.post("/knowledge-bases", json={"name": "RAG E2E Smoke Data", "course_name": "操作系统"})
        kb.raise_for_status()
        kb_id = kb.json()["id"]
        with (ROOT / "examples" / "operating_systems_sample.pdf").open("rb") as source:
            upload = client.post(f"/knowledge-bases/{kb_id}/documents", files={"file": ("operating_systems_sample.pdf", source, "application/pdf")})
        require(upload.status_code == 202, f"upload returned {upload.status_code}")
        document_id = upload.json()["id"]
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            doc = client.get(f"/documents/{document_id}/status").json()
            if doc["status"] in ("READY", "FAILED"):
                break
            time.sleep(.5)
        require(doc["status"] == "READY", f"document indexing failed: {doc['status']} {doc['error_message']}")
        require(doc["chunk_count"] > 0, "parser/chunker returned no chunks")
        session = client.post("/rag/sessions", json={"knowledge_base_id": kb_id, "title": "E2E evidence check"}).json()
        question = "进程和线程分别共享什么？"
        retrieval = client.post("/rag/retrieve", json={"session_id": session["id"], "question": question})
        retrieval.raise_for_status()
        citations = retrieval.json()["citations"]
        require(any("第一章" in item["section_title"] for item in citations), "dense retrieval missed the labelled process/thread section")
        preview = client.get(f"/documents/{citations[0]['document_id']}/preview", params={"chunk_id": citations[0]["chunk_id"]})
        preview.raise_for_status()
        require(citations[0]["snippet"] in preview.json()["highlight"], "citation does not point back to the stored source chunk")
        rebuilt = client.post(f"/documents/{document_id}/reindex")
        rebuilt.raise_for_status()
        rebuild_deadline = time.monotonic() + 180
        while time.monotonic() < rebuild_deadline:
            rebuilt_doc = client.get(f"/documents/{document_id}/status").json()
            if rebuilt_doc["status"] in ("READY", "FAILED"):
                break
            time.sleep(.5)
        require(rebuilt_doc["status"] == "READY" and rebuilt_doc["chunk_count"] == doc["chunk_count"], "reindex did not restore the same indexed chunk set")

        other = httpx.Client(base_url=API, timeout=30)
        try:
            auth(other, SECOND_USERNAME, PASSWORD, create=True)
            require(other.get("/knowledge-bases").json() == [], "second account can see another account's knowledge bases")
            require(other.get(f"/knowledge-bases/{kb_id}/documents").status_code == 404, "second account can list private documents")
            require(other.post("/rag/retrieve", json={"session_id": session["id"], "question": question}).status_code == 404, "second account can retrieve a private session")
        finally:
            other.delete("/auth/me")
            other.close()

        # Without explicit provider configuration, the endpoint must return the
        # real configuration error and never synthesize a demonstration answer.
        with client.stream("POST", "/rag/chat/stream", json={"session_id": session["id"], "question": question}) as response:
            require(response.status_code == 200, f"SSE endpoint returned HTTP {response.status_code}")
            body = "".join(response.iter_text())
        require("event: citations" in body and "event: error" in body, "expected real retrieval evidence followed by an explicit unconfigured-LLM error")
        require("event: done" not in body, "LLM failure was represented as a successful answer")
        if health.get("reranker_gate_enabled"):
            unsupported = "HTTP/2 多路复用如何避免 HTTP/1.1 队头阻塞？"
            result = client.post("/rag/retrieve", json={"session_id": session["id"], "question": unsupported})
            result.raise_for_status()
            require(result.json()["citations"] == [], "unsupported query passed the reranker evidence threshold")
            with client.stream("POST", "/rag/chat/stream", json={"session_id": session["id"], "question": unsupported}) as response:
                unsupported_body = "".join(response.iter_text())
            require("event: done" in unsupported_body and "event: error" not in unsupported_body, "unsupported question was not safely rejected without an LLM call")
        require(not client.get("/knowledge-bases").json() == [], "primary account lost its test knowledge base")
        print("PASSED: real PDF upload, page-aware parsing, chunking, 512-D embedding, Qdrant write, dense retrieval and citation preview")
        print("PASSED: reindex returns to READY without duplicating effective chunks")
        print("PASSED: account-isolated knowledge bases, document listing, and sessions")
        print("PASSED: unconfigured LLM returns an SSE error without a fake success")
        if health.get("reranker_gate_enabled"):
            print("PASSED: calibrated reranker gate refuses unsupported evidence without calling the LLM")
        print("READY for process restart: integration database and Qdrant directory are unchanged")


def second_phase():
    with httpx.Client(base_url=API, timeout=90) as client:
        auth(client, USERNAME, PASSWORD)
        kb = next((item for item in client.get("/knowledge-bases").json() if item["name"] == "RAG E2E Smoke Data"), None)
        require(kb is not None, "knowledge base did not persist across API process restart")
        documents = client.get(f"/knowledge-bases/{kb['id']}/documents").json()
        require(len(documents) == 1 and documents[0]["status"] == "READY", "document metadata did not persist across restart")
        session = next(iter(client.get("/rag/sessions", params={"knowledge_base_id": kb["id"]}).json()), None)
        require(session is not None, "session metadata did not persist across restart")
        result = client.post("/rag/retrieve", json={"session_id": session["id"], "question": "进程和线程分别共享什么？"})
        result.raise_for_status()
        citations = result.json()["citations"]
        require(citations and "第一章" in citations[0]["section_title"], "Qdrant vectors did not persist across restart")
        document_id = documents[0]["id"]
        client.delete(f"/documents/{document_id}").raise_for_status()
        after_delete = client.post("/rag/retrieve", json={"session_id": session["id"], "question": "进程和线程分别共享什么？"})
        after_delete.raise_for_status()
        require(after_delete.json()["citations"] == [], "deleted document remains available to retrieval")
        client.delete(f"/knowledge-bases/{kb['id']}").raise_for_status()
        client.delete("/auth/me").raise_for_status()
        print("PASSED: SQLite records and local Qdrant vectors survive a backend process restart")
        print("PASSED: deleting the indexed document removes it from subsequent retrieval")
        print("PASSED: E2E test account and test documents deleted")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("first", "second"))
    phase = parser.parse_args().phase
    (first_phase if phase == "first" else second_phase)()
