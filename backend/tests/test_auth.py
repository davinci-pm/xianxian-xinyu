from fastapi.testclient import TestClient

from app.main import app


def _login(client: TestClient, code: str) -> None:
    response = client.post("/api/v1/auth/login", json={"invite_code": code})
    assert response.status_code == 200
    assert response.json()["authenticated"] is True


def test_invalid_invite_code_is_rejected(client: TestClient) -> None:
    response = client.post("/api/v1/auth/login", json={"invite_code": "WRONG-CODE"})
    assert response.status_code == 401
    assert response.json()["detail"] == "邀请码无效"


def test_same_invite_code_restores_conversations_across_devices() -> None:
    with TestClient(app) as first_device, TestClient(app) as second_device:
        _login(first_device, "SAGE-ALPHA-001")
        created = first_device.post(
            "/api/v1/conversations", json={"persona_slug": "confucius"}
        )
        assert created.status_code == 201
        conversation_id = created.json()["conversation"]["id"]

        _login(second_device, "SAGE-ALPHA-001")
        restored = second_device.get(f"/api/v1/conversations/{conversation_id}")
        assert restored.status_code == 200


def test_different_invite_code_cannot_read_another_users_conversation() -> None:
    with TestClient(app) as first_user, TestClient(app) as second_user:
        _login(first_user, "SAGE-ALPHA-001")
        created = first_user.post(
            "/api/v1/conversations", json={"persona_slug": "confucius"}
        )
        conversation_id = created.json()["conversation"]["id"]

        _login(second_user, "SAGE-BETA-002")
        denied = second_user.get(f"/api/v1/conversations/{conversation_id}")
        assert denied.status_code == 404
