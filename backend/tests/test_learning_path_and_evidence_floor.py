import asyncio
from types import SimpleNamespace

from app.api import content_admin
from app.rag import pipeline


def test_evidence_floor_removes_each_low_scoring_candidate(monkeypatch):
    monkeypatch.setattr(
        pipeline,
        "get_settings",
        lambda: SimpleNamespace(
            min_evidence_score=0.78,
            max_evidence_per_document=3,
            max_evidence_per_section=2,
            final_evidence_count=5,
        ),
    )
    candidates = [
        {"chunk_id": "strong", "document_id": "doc", "section_title": "A", "content": "支持问题的证据内容。" * 10, "score": 0.7803},
        {"chunk_id": "weak", "document_id": "doc", "section_title": "B", "content": "低相关的候选内容。" * 10, "score": 0.7799},
        {"chunk_id": "irrelevant", "document_id": "doc", "section_title": "C", "content": "无关内容。" * 10, "score": -0.22},
    ]

    selected = pipeline.select_evidence(candidates)
    assert [item["chunk_id"] for item in selected] == ["strong"]


def test_answer_abstains_without_passing_below_floor_evidence_to_llm(monkeypatch):
    monkeypatch.setattr(
        pipeline,
        "get_settings",
        lambda: SimpleNamespace(
            min_evidence_score=0.78,
            max_evidence_per_document=3,
            max_evidence_per_section=2,
            final_evidence_count=5,
        ),
    )
    selected = pipeline.select_evidence([
        {"chunk_id": "off-topic", "document_id": "doc", "section_title": "other", "content": "LRU and CLOCK are unrelated to the user's question." * 3, "score": -0.22},
    ])
    assert selected == []

    def prepare(*_args):
        return [], [], "dense+rerank", selected

    def llm_must_not_run():
        raise AssertionError("LLM should not be called when evidence is below the calibrated floor")

    monkeypatch.setattr(pipeline, "prepare", prepare)
    monkeypatch.setattr(pipeline, "_client", llm_must_not_run)
    session = SimpleNamespace(answer_mode="library")
    answer, citations, _mode = asyncio.run(pipeline.answer(None, None, session, "unrelated question"))
    assert answer == pipeline.NO_EVIDENCE
    assert citations == []


def test_admin_content_crud_and_graph_personalized_path(client, monkeypatch):
    monkeypatch.setattr(content_admin, "get_settings", lambda: SimpleNamespace(content_admin_token="test-content-admin-token", content_admin_usernames="path_test_student"))
    registered = client.post(
        "/api/auth/register",
        json={"username": "path_test_student", "password": "long-test-password", "password_confirm": "long-test-password", "captcha_id": "00000000-0000-0000-0000-000000000000", "captcha_code": "ABCDE"},
    )
    assert registered.status_code == 201
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
    admin_headers = {**headers, "X-Content-Admin-Token": "test-content-admin-token"}

    course = client.post(
        "/api/admin/courses",
        headers=admin_headers,
        json={"id": "path-test-course", "name": "路径测试课程", "category": "测试", "points": 3},
    )
    assert course.status_code == 201
    for node in [
        {"id": "path-root", "name": "基础章节", "type": "chapter", "description": "基础内容"},
        {"id": "path-concept-a", "name": "基础概念", "type": "concept", "description": "前置概念"},
        {"id": "path-concept-b", "name": "应用概念", "type": "concept", "description": "后续概念"},
    ]:
        response = client.post(f"/api/admin/courses/path-test-course/nodes", headers=admin_headers, json=node)
        assert response.status_code == 201

    edges = client.put(
        "/api/admin/courses/path-test-course/edges",
        headers=admin_headers,
        json=[
            {"source": "path-root", "target": "path-concept-a"},
            {"source": "path-concept-a", "target": "path-concept-b"},
        ],
    )
    assert edges.status_code == 200
    mastery = client.put("/api/knowledge-mastery", headers=headers, json={"node_id": "path-concept-b", "mastery": 95})
    assert mastery.status_code == 200

    path = client.get("/api/me/courses/path-test-course/learning-path", headers=headers)
    assert path.status_code == 200
    result = path.json()
    ids = [step["nodeId"] for step in result["steps"]]
    assert ids.index("path-root") < ids.index("path-concept-a")
    assert "path-concept-b" not in ids
    assert result["progress"] == 50

    question = client.post(
        "/api/admin/questions",
        headers=admin_headers,
        json={"course_id": "path-test-course", "title": "概念检查题", "options": ["A", "B"], "answer": ["A"], "concept_id": "path-concept-a"},
    )
    assert question.status_code == 201
    listed = client.get("/api/admin/questions?course_id=path-test-course", headers=admin_headers)
    assert listed.status_code == 200
    assert any(item["answer"] == ["A"] for item in listed.json())

    attempt = client.post(
        "/api/quiz-attempts",
        headers=headers,
        json={"course_id": "path-test-course", "question_ids": [question.json()["id"]], "answers": {str(question.json()["id"]): ["A"]}},
    )
    assert attempt.status_code == 201
    course_progress = client.get("/api/courses", headers=headers)
    assert next(item["progress"] for item in course_progress.json() if item["id"] == "path-test-course") == 50
