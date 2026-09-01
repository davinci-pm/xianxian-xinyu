from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import (
    Conversation,
    KnowledgeDocument,
    Persona,
    PersonaClaim,
    PersonaCognitiveArtifact,
    PersonaEvaluation,
    PersonaEvidenceUnit,
    PersonaSourceFile,
    PersonaVersion,
)
from app.services.persona_distillation import _keywords, analyze_project_health


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
                f"小林：第{index + 1}次仍把短期结果当反馈；先做小实验，再决定是否投入。",
                "朋友：你最不愿意牺牲什么？",
                f"小林：第{index + 1}次我的底线没变：诚实和对家人的责任不能拿来交换。"
                "手机号是 13800138000，但这不该进入人物知识。",
            ]
        )
    return "\n".join(lines)


def test_keywords_keep_meaningful_chinese_phrases_intact() -> None:
    text = "稳定币是区块链基础设施。波场重视稳定币转账和区块链用户。" * 20

    keywords = _keywords(text)

    assert "稳定币" in keywords
    assert "区块链" in keywords
    assert "定币" not in keywords
    assert "块链" not in keywords


def test_high_quality_health_only_recommends_actual_weak_dimension() -> None:
    line = "孙宇晨：如果短期收入与用户体验冲突，我会选择降低成本，验证长期采用结果。"
    source = PersonaSourceFile(
        project_id="health-test",
        filename="sun-interview.txt",
        content="\n".join(line for _ in range(1_300)),
        char_count=len(line) * 1_300,
        content_hash="health-test-source",
        target_speaker="孙宇晨",
        source_type="public_statements",
        mime_type="text/plain",
        time_range="2018-2026",
        source_url=None,
        published_at=None,
        rights_confirmed=True,
    )
    calibration = {
        "core_values": "长期采用",
        "decision_case": "降低成本换取长期用户增长",
        "never_do": "不承诺收益",
        "unlike_response": "只讲空话",
    }

    health = analyze_project_health([source], calibration)

    assert health["overall_score"] >= 80
    assert health["readiness_level"] == "推荐版"
    assert health["fidelity_validated"] is False
    assert any("不同类型" in gap for gap in health["gaps"])
    assert all("说话人" not in gap for gap in health["gaps"])
    assert all("时间范围" not in gap for gap in health["gaps"])


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
            "source_url": "https://example.com/xiaolin-interview",
            "published_at": "2026-06-18",
            "rights_confirmed": True,
        },
    )
    assert uploaded.status_code == 201
    assert uploaded.json()["char_count"] > 800
    assert uploaded.json()["source_url"] == "https://example.com/xiaolin-interview"
    assert uploaded.json()["published_at"] == "2026-06-18"

    calibration = {
        "core_values": "诚实、长期投入、家庭责任",
        "decision_case": "面对新机会时先做小实验，根据反馈决定是否长期投入。",
        "never_do": "不会用虚假的短期成绩换取信任。",
        "unlike_response": "不经分析就斩钉截铁替别人做决定。",
    }
    health = client.post(
        f"/api/v1/studio/projects/{project_id}/health",
        json=calibration,
    )
    assert health.status_code == 200
    health_payload = health.json()
    assert health_payload["can_distill"] is True
    assert health_payload["decision_signals"] >= 20
    assert health_payload["overall_score"] >= 60
    assert len(health_payload["dimensions"]) == 6
    assert health_payload["recommended_questions"]

    distilled = client.post(
        f"/api/v1/studio/projects/{project_id}/distill",
        json=calibration,
    )
    assert distilled.status_code == 200
    payload = distilled.json()
    slug = payload["persona"]["slug"]
    assert payload["version"] == "1.0.0"
    assert payload["quality_score"] >= 65
    assert payload["project"]["claims"]
    assert payload["pipeline"]["pipeline_version"] == "nuwa-soul-v3"
    assert [stage["key"] for stage in payload["pipeline"]["stages"]] == [
        "evidence",
        "cognition",
        "retrieval",
        "generation",
        "learning",
    ]
    assert payload["pipeline"]["evaluation"]["case_count"] > 6
    assert payload["pipeline"]["evaluation"]["holdout_count"] > 0

    pipeline = client.get(f"/api/v1/studio/projects/{project_id}/pipeline")
    assert pipeline.status_code == 200
    assert pipeline.json()["status"] == "completed"
    assert pipeline.json()["evaluation_score"] > 0
    assert pipeline.json()["artifact_counts"]["decision"] > 0

    owned = client.get("/api/v1/me/personas")
    assert owned.status_code == 200
    assert any(item["slug"] == slug for item in owned.json())
    assert slug not in {item["slug"] for item in client.get("/api/v1/personas").json()}

    detail = client.get(f"/api/v1/personas/{slug}")
    assert detail.status_code == 200
    assert detail.json()["sources"][0]["title"] == "xiaolin-chat.txt"

    conversation = client.post("/api/v1/conversations", json={"persona_slug": slug})
    assert conversation.status_code == 201
    conversation_payload = conversation.json()["conversation"]
    assert "。，" not in conversation_payload["messages"][0]["content"]
    conversation_id = conversation_payload["id"]
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
        claim = db.scalar(
            select(PersonaClaim).where(
                PersonaClaim.project_id == project_id,
                PersonaClaim.claim_type == "principle",
            )
        )
        assert claim is not None
        assert '"creator_calibration"' in claim.evidence_json
        assert '"excerpt"' in claim.evidence_json
        evidence_units = list(
            db.scalars(
                select(PersonaEvidenceUnit).where(PersonaEvidenceUnit.project_id == project_id)
            )
        )
        assert evidence_units
        assert all(
            unit.source_url == "https://example.com/xiaolin-interview" for unit in evidence_units
        )
        assert any(unit.time_range for unit in evidence_units)
        artifacts = list(
            db.scalars(
                select(PersonaCognitiveArtifact).where(
                    PersonaCognitiveArtifact.project_id == project_id
                )
            )
        )
        assert {artifact.artifact_type for artifact in artifacts} >= {
            "value",
            "decision",
            "conditional_rule",
        }
        assert all(
            artifact.evidence_json != "[]"
            for artifact in artifacts
            if artifact.artifact_type != "correction"
        )
        evaluation = db.scalar(
            select(PersonaEvaluation).where(PersonaEvaluation.project_id == project_id)
        )
        assert evaluation is not None
        assert evaluation.suite_version == "soul-eval-v2"
        assert any(
            case.get("excluded_from_training")
            for case in __import__("json").loads(evaluation.cases_json)
        )

    feedback = client.post(
        f"/api/v1/studio/projects/{project_id}/feedback",
        json={
            "feedback_type": "missing_context",
            "content": "他在家庭责任与工作冲突时，会先确认家人的不可替代需求。",
        },
    )
    assert feedback.status_code == 201
    feedback_id = feedback.json()["id"]
    assert feedback.json()["status"] == "pending"
    reviewed = client.post(
        f"/api/v1/studio/projects/{project_id}/feedback/{feedback_id}/review",
        json={"action": "approve", "review_note": "创建者确认这是稳定规则"},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "approved"

    redistilled = client.post(f"/api/v1/studio/projects/{project_id}/regenerate")
    assert redistilled.status_code == 200
    assert redistilled.json()["version"] == "1.1.0"
    with SessionLocal() as db:
        persona = db.scalar(select(Persona).where(Persona.slug == slug))
        assert persona is not None
        current_version = db.get(PersonaVersion, persona.current_version_id)
        assert current_version is not None
        assert "家人的不可替代需求" in current_version.snapshot_json

    with TestClient(client.app) as other_user:
        _login(other_user, "SAGE-BETA-002")
        assert other_user.get(f"/api/v1/studio/projects/{project_id}").status_code == 404
        assert other_user.get(f"/api/v1/personas/{slug}").status_code == 404
        assert (
            other_user.post("/api/v1/conversations", json={"persona_slug": slug}).status_code == 404
        )
