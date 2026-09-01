import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import KnowledgeChunk, Persona, PersonaEvaluation, PersonaVersion
from app.services.web_facts import WebFact

FIXTURES = Path(__file__).parent / "fixtures"


def _events(body: str) -> list[tuple[str, dict]]:
    parsed: list[tuple[str, dict]] = []
    for block in body.replace("\r\n", "\n").split("\n\n"):
        event = next(
            (line[6:].strip() for line in block.splitlines() if line.startswith("event:")),
            "message",
        )
        data = "\n".join(
            line[5:].strip() for line in block.splitlines() if line.startswith("data:")
        )
        if data:
            parsed.append((event, json.loads(data)))
    return parsed


def test_soul_v3_full_wechat_distillation_and_dialogue_path(
    client: TestClient, monkeypatch: Any
) -> None:
    login = client.post("/api/v1/auth/login", json={"invite_code": "SAGE-ALPHA-001"})
    assert login.status_code == 200
    project = client.post(
        "/api/v1/studio/projects",
        json={
            "name": "林舟",
            "target_type": "authorized_private",
            "relationship": "长期朋友",
            "purpose": "在产品和人生取舍中复现他基于证据做小实验的判断方式。",
            "language": "zh-CN",
        },
    ).json()
    corpus = (FIXTURES / "wechat_soul_v3.txt").read_text(encoding="utf-8")
    uploaded = client.post(
        f"/api/v1/studio/projects/{project['id']}/sources",
        json={
            "filename": "wechat-soul-v3.txt",
            "source_type": "chat",
            "mime_type": "text/plain",
            "content": corpus,
            "target_speaker": "林舟",
            "time_range": "2025",
            "rights_confirmed": True,
        },
    )
    assert uploaded.status_code == 201
    calibration = {
        "core_values": "诚实、证据、长期用户价值",
        "decision_case": "短期增长与长期留存冲突时，先验证真实使用信号。",
        "never_do": "不拿漂亮数字冒充价值，不隐瞒坏消息。",
        "unlike_response": "不要空泛地说继续努力，也不要替别人保证结果。",
    }
    health = client.post(
        f"/api/v1/studio/projects/{project['id']}/health", json=calibration
    ).json()
    assert health["adaptive_tier"] in {"structured", "deep", "trainable"}
    assert health["data_profile"]["holdout_ready"] is True
    assert "blind_holdout" in health["enabled_capabilities"]
    assert health["fidelity_validated"] is False

    distilled = client.post(
        f"/api/v1/studio/projects/{project['id']}/distill", json=calibration
    )
    assert distilled.status_code == 200
    payload = distilled.json()
    assert payload["pipeline"]["pipeline_version"] == "nuwa-soul-v3"
    assert payload["pipeline"]["evaluation"]["holdout_count"] >= 1
    slug = payload["persona"]["slug"]

    with SessionLocal() as db:
        persona = db.scalar(select(Persona).where(Persona.slug == slug))
        assert persona is not None
        evaluation = db.scalar(
            select(PersonaEvaluation).where(PersonaEvaluation.project_id == project["id"])
        )
        assert evaluation is not None
        cases = json.loads(evaluation.cases_json)
        held_out = [case for case in cases if case["category"] == "dialogue_holdout"]
        assert held_out
        indexed = "\n".join(
            db.scalars(
                select(KnowledgeChunk.content).where(KnowledgeChunk.persona_id == persona.id)
            )
        )
        assert all(case["expected_response"] not in indexed for case in held_out)
        version = db.get(PersonaVersion, persona.current_version_id)
        assert version is not None
        assert all(
            case["expected_response"] not in version.snapshot_json for case in held_out
        )

    conversation = client.post("/api/v1/conversations", json={"persona_slug": slug}).json()
    response = client.post(
        f"/api/v1/conversations/{conversation['conversation']['id']}/messages/stream",
        json={
            "content": "短期收入和长期用户价值冲突时，我该怎么选？",
            "idempotency_key": "soul-v3-e2e-001",
        },
    )
    assert response.status_code == 200
    events = _events(response.text)
    meta = next(data for event, data in events if event == "meta")
    answer = "".join(data.get("text", "") for event, data in events if event == "chunk")
    assert meta["generation_plan"]["deliberation_required"] is True
    assert meta["generation_plan"]["activated_persona_assets"]
    assert "按这些资料呈现的判断方式" in answer
    assert events[-1][0] == "done"

    async def current_facts(_persona_name: str, _user_text: str) -> list[WebFact]:
        assert _persona_name == "林舟"
        return [
            WebFact(
                id="web-soul-v3-test",
                title="公开机构发布林舟项目最新进展",
                summary="公开文件显示项目完成一轮产品测试。",
                source_url="https://www.sec.gov/example-soul-v3",
                source_domain="sec.gov",
                published_at="2026-08-31T08:00:00+00:00",
                retrieved_at=datetime.now(UTC).isoformat(),
                trust="high",
            )
        ]

    monkeypatch.setattr("app.api.v1.router.search_current_facts", current_facts)
    recent = client.post(
        f"/api/v1/conversations/{conversation['conversation']['id']}/messages/stream",
        json={
            "content": "最近关于林舟发生了什么公开新闻？",
            "idempotency_key": "soul-v3-e2e-002",
        },
    )
    recent_events = _events(recent.text)
    recent_meta = next(data for event, data in recent_events if event == "meta")
    recent_done = next(data for event, data in recent_events if event == "done")
    assert recent_meta["web"]["used"] is True
    assert recent_meta["generation_plan"]["web_fact_count"] == 1
    assert any(
        item["label"].startswith("联网公开资料")
        for item in recent_done["message"]["citations"]
    )
