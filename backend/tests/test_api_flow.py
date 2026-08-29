import json
from typing import Any

from fastapi.testclient import TestClient


def parse_sse(body: str) -> list[tuple[str, dict[str, Any]]]:
    events = []
    for block in body.replace("\r\n", "\n").split("\n\n"):
        if not block.strip():
            continue
        lines = block.splitlines()
        event = next(
            line.removeprefix("event:").strip() for line in lines if line.startswith("event:")
        )
        data = "\n".join(
            line.removeprefix("data:").strip() for line in lines if line.startswith("data:")
        )
        events.append((event, json.loads(data)))
    return events


def create_confucius_conversation(client: TestClient) -> dict[str, Any]:
    response = client.post("/api/v1/conversations", json={"persona_slug": "confucius"})
    assert response.status_code == 201
    payload: dict[str, Any] = response.json()
    return payload


def test_cards_detail_opening_followup_and_restore(client: TestClient) -> None:
    cards = client.get("/api/v1/personas")
    assert cards.status_code == 200
    card_slugs = {item["slug"] for item in cards.json()}
    assert len(card_slugs) == 19
    assert {
        "confucius",
        "fengge-wangmingtianya",
        "marcus-aurelius",
        "nietzsche",
        "steve-jobs",
        "zhang-xuefeng",
        "richard-feynman",
        "charlie-munger",
    }.issubset(card_slugs)

    detail = client.get("/api/v1/personas/confucius")
    assert detail.status_code == 200
    assert len(detail.json()["principles"]) >= 4
    assert detail.json()["sources"]

    created = create_confucius_conversation(client)
    conversation_id = created["conversation"]["id"]
    opening = created["opening_message"]["content"]
    assert "有什么可以帮你" not in opening
    assert "拿不定主意" in opening

    streamed = client.post(
        f"/api/v1/conversations/{conversation_id}/messages/stream",
        json={"content": "我希望转行做AI产品经理，但担心失败", "idempotency_key": "flow-test-0001"},
    )
    assert streamed.status_code == 200
    events = parse_sse(streamed.text)
    assert [name for name, _ in events][0] == "meta"
    assert events[0][1]["intent"]["primary_intent"] == "career"
    assert events[0][1]["intent"]["model"] == "heuristic-intent-v1"
    assert events[0][1]["performance"]["preprocessing_ms"] >= 0
    assert "chunk" in [name for name, _ in events]
    assert [name for name, _ in events][-1] == "done"
    candidate = events[0][1]["memory_candidate"]
    assert candidate["status"] == "pending"
    assistant = events[-1][1]["message"]
    assert assistant["role"] == "assistant"
    assert assistant["content"]
    assert events[-1][1]["performance"]["first_chunk_ms"] >= 0
    assert events[-1][1]["performance"]["total_ms"] >= 0

    restored = client.get(f"/api/v1/conversations/{conversation_id}")
    assert restored.status_code == 200
    assert len(restored.json()["messages"]) == 3
    assert restored.json()["short_summary"]

    confirmed = client.post(
        f"/api/v1/memories/{candidate['id']}/confirm", json={"action": "remember"}
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["scope"] == "long_term"

    next_conversation = create_confucius_conversation(client)
    assert next_conversation["remembered_context"]
    assert "AI产品经理" in next_conversation["opening_message"]["content"]


def test_only_important_memory_is_offered(client: TestClient) -> None:
    created = create_confucius_conversation(client)
    conversation_id = created["conversation"]["id"]
    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages/stream",
        json={"content": "我希望你直接一点回答", "idempotency_key": "no-memory-0001"},
    )
    events = parse_sse(response.text)
    assert events[0][1]["intent"]["memory_should_offer"] is False
    assert events[0][1]["memory_candidate"] is None


def test_long_term_memory_can_be_edited_paused_resumed_and_deleted(
    client: TestClient,
) -> None:
    created = create_confucius_conversation(client)
    conversation_id = created["conversation"]["id"]
    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages/stream",
        json={
            "content": "我计划明年转行做产品经理",
            "idempotency_key": "memory-crud-0001",
        },
    )
    candidate = parse_sse(response.text)[0][1]["memory_candidate"]
    confirmed = client.post(
        f"/api/v1/memories/{candidate['id']}/confirm", json={"action": "remember"}
    )
    assert confirmed.status_code == 200

    edited = client.patch(
        f"/api/v1/memories/{candidate['id']}",
        json={"content": "我计划明年转行做教育产品经理"},
    )
    assert edited.status_code == 200
    assert edited.json()["content"] == "我计划明年转行做教育产品经理"

    paused = client.patch(
        f"/api/v1/memories/{candidate['id']}", json={"paused": True}
    )
    assert paused.json()["status"] == "paused"
    while_paused = create_confucius_conversation(client)
    assert while_paused["remembered_context"] == []

    resumed = client.patch(
        f"/api/v1/memories/{candidate['id']}", json={"paused": False}
    )
    assert resumed.json()["status"] == "confirmed"
    after_resume = create_confucius_conversation(client)
    assert "教育产品经理" in after_resume["opening_message"]["content"]

    deleted = client.delete(f"/api/v1/memories/{candidate['id']}")
    assert deleted.status_code == 204
    assert all(item["id"] != candidate["id"] for item in client.get("/api/v1/memories").json())


def test_long_term_memory_is_isolated_by_persona(client: TestClient) -> None:
    created = create_confucius_conversation(client)
    conversation_id = created["conversation"]["id"]
    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages/stream",
        json={
            "content": "我的目标是今年读完十二本经典",
            "idempotency_key": "memory-scope-0001",
        },
    )
    candidate = parse_sse(response.text)[0][1]["memory_candidate"]
    client.post(f"/api/v1/memories/{candidate['id']}/confirm", json={"action": "remember"})

    nietzsche = client.post(
        "/api/v1/conversations", json={"persona_slug": "nietzsche"}
    )
    assert nietzsche.status_code == 201
    assert nietzsche.json()["remembered_context"] == []


def test_safety_response_stops_role_play(client: TestClient) -> None:
    created = create_confucius_conversation(client)
    conversation_id = created["conversation"]["id"]
    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages/stream",
        json={"content": "我不想活了，想结束生命", "idempotency_key": "safety-test-001"},
    )
    events = parse_sse(response.text)
    assert events[0][1]["stage"] == "SAFETY"
    assert events[0][1]["safety_level"] == "L3"
    assert "暂停人物角色" in events[-1][1]["message"]["content"]

    recovered = client.post(
        f"/api/v1/conversations/{conversation_id}/messages/stream",
        json={"content": "我现在安全", "idempotency_key": "safety-recovery-001"},
    )
    recovered_events = parse_sse(recovered.text)
    assert recovered_events[0][1]["stage"] == "CLARIFY"
    assert recovered_events[0][1]["safety_status"] == "recovered"
    assert "输入已经恢复" in recovered_events[-1][1]["message"]["content"]

    continued = client.post(
        f"/api/v1/conversations/{conversation_id}/messages/stream",
        json={"content": "我现在想谈谈工作", "idempotency_key": "safety-continued-001"},
    )
    continued_events = parse_sse(continued.text)
    assert continued_events[0][1]["stage"] == "GUIDANCE"
    assert continued_events[-1][1]["message"]["content"]


def test_immediate_danger_confirmation_keeps_safety_mode(client: TestClient) -> None:
    created = create_confucius_conversation(client)
    conversation_id = created["conversation"]["id"]
    client.post(
        f"/api/v1/conversations/{conversation_id}/messages/stream",
        json={"content": "我不想活了", "idempotency_key": "danger-entry-001"},
    )
    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages/stream",
        json={"content": "我有立即行动的打算", "idempotency_key": "danger-confirm-001"},
    )
    events = parse_sse(response.text)
    assert events[0][1]["stage"] == "SAFETY"
    assert events[0][1]["safety_level"] == "L3"
    restored = client.get(f"/api/v1/conversations/{conversation_id}")
    assert restored.json()["stage"] == "SAFETY"


def test_model_failure_returns_visible_persona_fallback(
    client: TestClient, monkeypatch: Any
) -> None:
    def fail_provider() -> None:
        raise RuntimeError("synthetic provider outage")

    monkeypatch.setattr("app.api.v1.router.get_model_provider", fail_provider)
    created = create_confucius_conversation(client)
    conversation_id = created["conversation"]["id"]
    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages/stream",
        json={"content": "我最近很迷茫", "idempotency_key": "fallback-test-1"},
    )
    events = parse_sse(response.text)
    assert "degraded" in [name for name, _ in events]
    assert events[-1][1]["degraded"] is True
    assert events[-1][1]["message"]["content"]


def test_empty_model_content_retries_once_before_fallback(
    client: TestClient, monkeypatch: Any
) -> None:
    class EmptyThenSuccessProvider:
        name = "empty-then-success"
        model = "test-model"

        def __init__(self) -> None:
            self.calls = 0

        async def stream(self, context: Any) -> Any:
            self.calls += 1
            if self.calls == 2:
                yield "第二次已正常返回。"

    provider = EmptyThenSuccessProvider()
    monkeypatch.setattr("app.api.v1.router.get_model_provider", lambda: provider)
    created = create_confucius_conversation(client)
    conversation_id = created["conversation"]["id"]
    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages/stream",
        json={"content": "请帮我拆解这个选择", "idempotency_key": "empty-retry-test-1"},
    )
    events = parse_sse(response.text)
    assert provider.calls == 2
    assert "retry" in [name for name, _ in events]
    assert "degraded" not in [name for name, _ in events]
    assert events[-1][1]["message"]["content"] == "第二次已正常返回。"


def test_memory_candidate_is_committed_before_model_stream_and_user_is_not_duplicated(
    client: TestClient, monkeypatch: Any
) -> None:
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models import Memory

    captured: dict[str, Any] = {}

    class InspectingProvider:
        name = "transaction-inspector"
        model = "test-model"

        async def stream(self, context: Any) -> Any:
            captured["recent_messages"] = context.recent_messages
            with SessionLocal() as independent_db:
                captured["candidate"] = independent_db.scalar(
                    select(Memory).where(
                        Memory.conversation_id == captured["conversation_id"],
                        Memory.status == "pending",
                    )
                )
            yield "已经接住你的问题。"

    monkeypatch.setattr("app.api.v1.router.get_model_provider", InspectingProvider)
    created = create_confucius_conversation(client)
    conversation_id = created["conversation"]["id"]
    captured["conversation_id"] = conversation_id
    current_text = "我希望做一个AI产品，但担心方向不对"

    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages/stream",
        json={"content": current_text, "idempotency_key": "memory-commit-before-stream"},
    )

    assert response.status_code == 200
    assert captured["candidate"] is not None
    assert all(item["content"] != current_text for item in captured["recent_messages"])


def test_skill_allowlist_is_visible(client: TestClient) -> None:
    response = client.get("/api/v1/skills")
    assert response.status_code == 200
    skills = {item["skill_key"]: item for item in response.json()}
    assert skills["reflective_question"]["allowlisted"] is True
    assert skills["fengge_perspective_reviewed"]["allowlisted"] is True
    assert skills["fengge_perspective_reviewed"]["license_name"] == "MIT"
    assert skills["fengge_perspective_reviewed"]["risk_level"] == "medium"
    assert skills["github_unreviewed_example"]["allowlisted"] is False
    assert skills["github_unreviewed_example"]["enabled"] is False


def test_original_fengge_skill_is_loaded_for_persona_flow(client: TestClient) -> None:
    detail = client.get("/api/v1/personas/fengge-wangmingtianya")
    assert detail.status_code == 200
    assert detail.json()["is_living"] is True
    assert "非授权" in detail.json()["disclaimer"]

    created = client.post(
        "/api/v1/conversations", json={"persona_slug": "fengge-wangmingtianya"}
    )
    assert created.status_code == 201
    assert "有什么可以帮你" not in created.json()["opening_message"]["content"]
    conversation_id = created.json()["conversation"]["id"]

    streamed = client.post(
        f"/api/v1/conversations/{conversation_id}/messages/stream",
        json={
            "content": "我想辞职，但不知道是真想走还是在逃避",
            "idempotency_key": "fengge-flow-0001",
        },
    )
    assert streamed.status_code == 200
    events = parse_sse(streamed.text)
    assert events[0][1]["applied_skills"] == ["fengge_perspective_reviewed"]
    assert events[0][1]["applied_skill_modes"] == {
        "fengge_perspective_reviewed": "upstream_original"
    }
    assistant = events[-1][1]["message"]["content"]
    assert assistant
    assert "兄弟" in assistant
    assert "我就是峰哥" not in assistant


def test_vendored_upstream_persona_uses_read_only_original_skill(
    client: TestClient,
) -> None:
    detail = client.get("/api/v1/personas/steve-jobs")
    assert detail.status_code == 200
    assert "AI 思想人格" in detail.json()["disclaimer"]

    created = client.post("/api/v1/conversations", json={"persona_slug": "steve-jobs"})
    assert created.status_code == 201
    conversation_id = created.json()["conversation"]["id"]
    streamed = client.post(
        f"/api/v1/conversations/{conversation_id}/messages/stream",
        json={
            "content": "我的产品功能越来越多，但用户还是不愿意用",
            "idempotency_key": "steve-jobs-upstream-001",
        },
    )
    events = parse_sse(streamed.text)
    assert events[0][1]["applied_skills"] == ["upstream_steve_jobs"]
    assert events[0][1]["applied_skill_modes"] == {
        "upstream_steve_jobs": "upstream_original_read_only"
    }
