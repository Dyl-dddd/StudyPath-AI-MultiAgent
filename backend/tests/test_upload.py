def test_unsupported_upload_extension_is_rejected(client):
    account = client.post("/api/auth/register", json={"username": "upload_test", "password": "upload-test-passphrase-long", "password_confirm": "upload-test-passphrase-long", "captcha_id": "00000000-0000-0000-0000-000000000000", "captcha_code": "ABCDE"})
    token = account.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    kb = client.post("/api/knowledge-bases", headers=headers, json={"name": "upload test", "course_name": ""}).json()
    response = client.post(f"/api/knowledge-bases/{kb['id']}/documents", headers=headers, files={"file": ("payload.exe", b"not a course document", "application/octet-stream")})
    assert response.status_code == 415
    assert client.get(f"/api/knowledge-bases/{kb['id']}/documents", headers=headers).json() == []
