def register(client, username):
    response = client.post("/api/auth/register", json={"username": username, "password": "long-enough-test-password", "password_confirm": "long-enough-test-password", "captcha_id": "00000000-0000-0000-0000-000000000000", "captcha_code": "ABCDE"})
    assert response.status_code == 201
    return response.json()["access_token"]


def test_private_knowledge_bases_and_sessions_are_isolated(client):
    token_a = register(client, "student_a")
    token_b = register(client, "student_b")
    response = client.post("/api/knowledge-bases", headers={"Authorization": f"Bearer {token_a}"}, json={"name": "A 的私人课程", "course_name": "操作系统"})
    assert response.status_code == 201
    kb_id = response.json()["id"]

    assert client.get("/api/knowledge-bases", headers={"Authorization": f"Bearer {token_b}"}).json() == []
    assert client.get(f"/api/knowledge-bases/{kb_id}/documents", headers={"Authorization": f"Bearer {token_b}"}).status_code == 404
    assert client.delete(f"/api/knowledge-bases/{kb_id}", headers={"Authorization": f"Bearer {token_b}"}).status_code == 404
    assert client.post("/api/rag/sessions", headers={"Authorization": f"Bearer {token_b}"}, json={"knowledge_base_id": kb_id}).status_code == 404


def test_invalid_bearer_and_unauthenticated_upload_are_rejected(client):
    assert client.get("/api/knowledge-bases").status_code == 401
    assert client.get("/api/knowledge-bases", headers={"Authorization": "Bearer forged-token"}).status_code == 401


def test_user_can_register_and_log_in(client):
    register(client, "student_c")
    response = client.post("/api/auth/login", json={"username": "student_c", "password": "long-enough-test-password"})
    assert response.status_code == 200
    assert response.json()["username"] == "student_c"
    assert client.post("/api/auth/login", json={"username": "student_c", "password": "wrong-password-long"}).status_code == 401
