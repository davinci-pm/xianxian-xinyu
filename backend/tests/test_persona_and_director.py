from app.services.conversation_director import DialogueStage, conversation_director
from app.services.persona_loader import load_persona_pack
from app.services.safety import assess_safety


def test_complete_confucius_pack_is_structured() -> None:
    pack = load_persona_pack("confucius")
    assert pack.manifest["tier"] == "A"
    assert len(pack.manifest["principles"]) >= 4
    assert pack.manifest["proactive_strategy"]["max_question_streak"] == 2
    assert pack.sources
    assert pack.starters[0]["quick_replies"]


def test_fengge_pack_uses_only_upstream_original_skill() -> None:
    pack = load_persona_pack("fengge-wangmingtianya")
    assert pack.profile["is_living"] is True
    assert pack.manifest["skills"] == ["fengge_perspective_reviewed"]
    assert "原版峰哥" in pack.profile["short_intro"]
    assert "非授权" in pack.manifest["disclaimer"]
    assert all("github_unreviewed_example" != key for key in pack.manifest["skills"])


def test_dialogue_director_covers_required_stages() -> None:
    stage = conversation_director.next_stage("BREAK_ICE", "我最近有点迷茫", 0)
    assert stage == DialogueStage.IDENTIFY_PROBLEM
    stage = conversation_director.next_stage(stage, "主要是工作", 1)
    assert stage == DialogueStage.CLARIFY
    stage = conversation_director.next_stage(stage, "我怕做错", 2)
    assert stage == DialogueStage.GUIDANCE
    stage = conversation_director.next_stage(stage, "我愿意试试", 0)
    assert stage == DialogueStage.REFLECTION
    assert conversation_director.next_stage(stage, "今天先这样", 0) == DialogueStage.END


def test_high_risk_signal_breaks_role() -> None:
    assessment = assess_safety("我现在就要结束生命，马上会行动")
    assert assessment.level == "L3"
    assert assessment.should_break_role is True
