from app.agents.roles import resolve_intent
from app.agents.contracts import AgentRunInput


def _register(client, username):
    response = client.post("/api/auth/register", json={
        "username": username,
        "password": "long-enough-agent-test-password",
        "password_confirm": "long-enough-agent-test-password",
        "captcha_id": "00000000-0000-0000-0000-000000000000",
        "captcha_code": "ABCDE",
    })
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_orchestrator_resolves_only_bounded_supported_intents():
    assert resolve_intent(AgentRunInput(question_id=9)) == "mistake"
    assert resolve_intent(AgentRunInput(session_id="owned-session")) == "local_qa"
    assert resolve_intent(AgentRunInput(question="分析知识图谱中的先修关系")) == "graph"
    assert resolve_intent(AgentRunInput(question="看看我的薄弱点和学习计划")) == "profile"
    assert resolve_intent(AgentRunInput(question="解释什么是进程")) == "tutor"


def test_agent_health_is_authenticated_and_never_returns_provider_credentials(client):
    assert client.get("/api/agents/health").status_code == 401
    headers = _register(client, "agent_health_student")
    response = client.get("/api/agents/health", headers=headers)
    assert response.status_code == 200
    result = response.json()
    assert set(result["roles"]) == {"user_profile", "mistake_transfer", "course_rag", "general_tutor", "knowledge_graph"}
    assert result["providers"]["agentharness"]["execution_enabled"] is False
    assert "key" not in str(result).lower()


def test_profile_fields_are_persisted_per_user_and_reject_unknown_stage(client):
    headers_a = _register(client, "agent_profile_student_a")
    headers_b = _register(client, "agent_profile_student_b")
    saved = client.patch("/api/profile", headers=headers_a, json={
        "educationStage": "高中", "grade": "高二", "learningSubjects": ["数学", "计算机"],
        "learningGoal": "理解数据结构中的树与图",
    })
    assert saved.status_code == 200
    assert saved.json()["educationStage"] == "高中"
    assert saved.json()["learningSubjects"] == ["数学", "计算机"]
    assert saved.json()["learningGoal"] == "理解数据结构中的树与图"
    assert client.get("/api/profile", headers=headers_b).json()["educationStage"] == "大学"
    assert client.patch("/api/profile", headers=headers_a, json={"educationStage": "未知学段"}).status_code == 422


def test_profile_agent_uses_account_data_and_handles_empty_state_without_mock(client):
    headers = _register(client, "agent_profile_empty")
    response = client.post("/api/agents/run", headers=headers, json={"intent": "profile"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "partial"
    assert body["intent"] == "profile"
    assert body["evidence"] == []
    assert "没有足够" in body["result"]["message"]


def test_parallel_orchestration_rejects_write_capable_or_unknown_roles(client):
    headers = _register(client, "agent_parallel_student")
    response = client.post("/api/agents/run/parallel", headers=headers, json={"intents": ["profile", "mistake"]})
    assert response.status_code == 422


def test_parallel_readonly_orchestration_returns_partial_results_per_role(client):
    headers = _register(client, "agent_parallel_readonly_student")
    response = client.post("/api/agents/run/parallel", headers=headers, json={
        "intents": ["profile", "graph"], "course_id": "missing-course",
    })
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "partial"
    assert {result["intent"] for result in body["results"]} == {"profile", "graph"}
    graph = next(result for result in body["results"] if result["intent"] == "graph")
    assert graph["status"] == "failed"
    assert graph["error"]["code"] == "http_404"
    assert body["merged"]["profile"] is not None
    assert body["merged"]["graph"] is None
    assert body["merged"]["errors"] == [{
        "intent": "graph", "code": "http_404", "message": "课程不存在",
    }]


def test_parallel_orchestration_marks_all_failed_when_no_agent_returns_data(client, monkeypatch):
    from fastapi import HTTPException
    from app.agents.orchestrator import ROLE_HANDLERS

    async def unavailable(*_args):
        raise HTTPException(503, "服务不可用")

    monkeypatch.setitem(ROLE_HANDLERS, "profile", unavailable)
    monkeypatch.setitem(ROLE_HANDLERS, "graph", unavailable)
    headers = _register(client, "agent_parallel_all_failed")
    response = client.post("/api/agents/run/parallel", headers=headers, json={
        "intents": ["profile", "graph"], "course_id": "any-course",
    })
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["merged"]["profile"] is None
    assert body["merged"]["graph"] is None
    assert len(body["merged"]["errors"]) == 2
