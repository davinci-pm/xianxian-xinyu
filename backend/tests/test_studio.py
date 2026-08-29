from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Conversation, KnowledgeDocument, Persona


def _login(client: TestClient, code: str) -> None:
    response = client.post("/api/v1/auth/login", json={"invite_code": code})
    assert response.status_code == 200


def _chat_corpus() -> str:
    lines = []
    for index in range(28):
        lines.extend(
            [
                f"小林：第{index + 1}次遇到选择时，我会先把事实写下来，再看哪一件事值得长期投入。",
                "朋友：如果短期没有结果呢？",
                "小林：短期结果只是反馈，不是判决。我会先做一个小实验，再决定要不要加大投入。",
                "朋友：你最不愿意牺牲什么？",
                "小林：诚实和对家人的责任不能拿来交换。"
                "手机号是 13800138000，但这不该进入人物知识。",
            ]
        )
    return "\n".join(lines)


def test_private_studio_builds_versioned_persona_and_keeps_it_isolated(
    client: TestClient,
) -> None:
    assert client.get("/api/v1/studio/projects").status_code == 401
    _login(client, "SAGE-ALPHA-001")

    created = client.post(
        "/api/v1/studio/projects",
        json={
            "name": "小林",
            "target_type": "authorized_private",
            "relationship": "朋友",
            "purpose": "在我遇到选择时，用他一贯的判断方式陪我分析。",
            "language": "zh-CN",
        },
    )
    assert created.status_code == 201
    project_id = created.json()["id"]

    uploaded = client.post(
        f"/api/v1/studio/projects/{project_id}/sources",
        json={
            "filename": "xiaolin-chat.txt",
            "source_type": "chat",
            "mime_type": "text/plain",
            "content": _chat_corpus(),
            "target_speaker": "小林",
            "time_range": "2024-2026",
            "rights_confirmed": True,
        },
    )
    assert uploaded.status_code == 201
    assert uploaded.json()["char_count"] > 800

    distilled = client.post(
        f"/api/v1/studio/projects/{project_id}/distill",
        json={
            "core_values": "诚实、长期投入、家庭责任",
            "decision_case": "面对新机会时先做小实验，根据反馈决定是否长期投入。",
            "never_do": "不会用虚假的短期成绩换取信任。",
            "unlike_response": "不经分析就斩钉截铁替别人做决定。",
        },
    )
    assert distilled.status_code == 200
    payload = distilled.json()
    slug = payload["persona"]["slug"]
    assert payload["version"] == "1.0.0"
    assert payload["quality_score"] >= 65
    assert payload["project"]["claims"]

    owned = client.get("/api/v1/me/personas")
    assert owned.status_code == 200
    assert any(item["slug"] == slug for item in owned.json())
    assert slug not in {item["slug"] for item in client.get("/api/v1/personas").json()}

    detail = client.get(f"/api/v1/personas/{slug}")
    assert detail.status_code == 200
    assert detail.json()["sources"][0]["title"] == "xiaolin-chat.txt"

    conversation = client.post("/api/v1/conversations", json={"persona_slug": slug})
    assert conversation.status_code == 201
    conversation_id = conversation.json()["conversation"]["id"]
    with SessionLocal() as db:
        stored_conversation = db.get(Conversation, conversation_id)
        assert stored_conversation is not None
        assert stored_conversation.persona_version_id is not None
        persona = db.scalar(select(Persona).where(Persona.slug == slug))
        assert persona is not None
        document = db.scalar(
            select(KnowledgeDocument).where(KnowledgeDocument.persona_id == persona.id)
        )
        assert document is not None
        assert "13800138000" not in document.content
        assert "[手机号已隐藏]" in document.content

    with TestClient(client.app) as other_user:
        _login(other_user, "SAGE-BETA-002")
        assert other_user.get(f"/api/v1/studio/projects/{project_id}").status_code == 404
        assert other_user.get(f"/api/v1/personas/{slug}").status_code == 404
        assert (
            other_user.post("/api/v1/conversations", json={"persona_slug": slug}).status_code
            == 404
        )
