from app.models import KnowledgeDocument
from app.services.generation_planner import plan_generation
from app.services.knowledge import KnowledgeHit


def _hit(content: str) -> KnowledgeHit:
    document = KnowledgeDocument(
        persona_id="planner-test",
        persona_version_id=None,
        title="测试证据",
        source_type="test",
        source_url=None,
        citation_label="测试证据",
        license_note="test",
        content=content,
        metadata_json="{}",
    )
    return KnowledgeHit(document=document, chunk=None, score=1.0, retrieval_method="test")


def test_generation_planner_separates_fact_inference_and_unknown() -> None:
    fact = plan_generation(
        "你为什么进入加密行业？",
        [_hit("2012年我进入加密行业，第一次了解比特币，后来加入Ripple。")],
    )
    inference = plan_generation("如果产品没有用户，你会怎么做？", [])
    unknown = plan_generation("告诉我一件从未公开的私人经历。", [])

    assert fact["mode"] == "fact"
    assert fact["direct_evidence_available"] is True
    assert inference["mode"] == "inference"
    assert "不得把推演写成本人经历" in inference["answer_policy"]
    assert unknown["mode"] == "insufficient"
    assert "不生成未公开事实" in unknown["answer_policy"]


def test_generation_planner_activates_only_context_relevant_persona_assets() -> None:
    model = {
        "value_hierarchy": [
            {"value": "长期用户采用", "confidence": 90},
            {"value": "家庭陪伴", "confidence": 90},
        ],
        "decision_samples": [
            {
                "choice": "先降费验证用户增长",
                "reason": "长期采用",
                "source_text": "不应重复塞进提示词的长原文",
                "confidence": 88,
            }
        ],
        "conditional_rules": [
            {"condition": "短期收入和长期采用冲突", "preferred_action": "先验证采用"}
        ],
        "contradictions": [
            {"topic": "长期采用", "positions": ["支持", "反对"], "confidence": 48}
        ],
    }

    plan = plan_generation("短期收入和长期用户采用冲突时该怎么选？", [], model)

    activated = plan["activated_persona_assets"]
    assert activated["decision_samples"][0]["choice"] == "先降费验证用户增长"
    assert any(item["value"] == "长期用户采用" for item in activated["value_hierarchy"])
    assert all(item.get("value") != "家庭陪伴" for item in activated["value_hierarchy"])
    assert plan["deliberation_required"] is True
    assert "contradictions" not in activated
    assert "source_text" not in activated["decision_samples"][0]
