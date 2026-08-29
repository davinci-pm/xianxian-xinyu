from types import SimpleNamespace
from typing import Any

from app.services.conversation_director import ConversationDirector, DialogueStage
from app.services.intent_classifier import HeuristicIntentClassifier, analyze_intent


async def test_heuristic_classifier_recognizes_career_anxiety() -> None:
    result = await HeuristicIntentClassifier().analyze(
        "我想辞职转行，但很担心失败，不知道该不该走", []
    )
    assert result.analysis.primary_intent == "career"
    assert result.analysis.emotion == "anxious"
    assert result.analysis.recommended_stage == "GUIDANCE"
    assert result.analysis.recommended_move == "action"
    assert result.analysis.should_ask_question is False
    assert result.analysis.memory_should_offer is True
    assert result.analysis.memory_kind == "goal"
    assert "辞职转行" in result.analysis.memory_content


async def test_heuristic_classifier_does_not_offer_transient_request() -> None:
    result = await HeuristicIntentClassifier().analyze("我希望你直接一点回答，不要列太多条目", [])
    assert result.analysis.memory_should_offer is False
    assert result.analysis.memory_kind == "none"
    assert result.analysis.memory_content == ""


async def test_heuristic_classifier_recognizes_explicit_end() -> None:
    result = await HeuristicIntentClassifier().analyze("今天先这样，下次再聊", [])
    assert result.analysis.primary_intent == "end"
    assert result.analysis.recommended_stage == "END"
    assert result.analysis.should_ask_question is False


async def test_heuristic_classifier_does_not_end_for_relationship_or_work() -> None:
    relationship = await HeuristicIntentClassifier().analyze(
        "这段关系让我绝望，我在考虑结束这段关系", []
    )
    work = await HeuristicIntentClassifier().analyze("我想结束这份工作，重新开始", [])
    assert relationship.analysis.primary_intent != "end"
    assert relationship.analysis.recommended_stage != "END"
    assert work.analysis.primary_intent != "end"
    assert work.analysis.recommended_stage != "END"


def test_director_uses_only_confident_model_recommendation() -> None:
    director = ConversationDirector()
    confident = {
        "confidence": 0.9,
        "recommended_stage": "GUIDANCE",
        "should_ask_question": False,
    }
    assert (
        director.next_stage("IDENTIFY_PROBLEM", "我已经想得很清楚", 0, confident)
        == DialogueStage.GUIDANCE
    )
    assert director.should_ask_question(DialogueStage.GUIDANCE, 0, confident) is False


def test_director_only_ends_for_explicit_conversation_end() -> None:
    director = ConversationDirector()
    assert director.next_stage("CLARIFY", "我在考虑结束这段关系", 0) == DialogueStage.GUIDANCE
    assert director.next_stage("CLARIFY", "请结束本次对话", 0) == DialogueStage.END


async def test_explicit_end_uses_zero_network_fast_path(monkeypatch: Any) -> None:
    settings = SimpleNamespace(
        intent_llm_enabled=True,
        intent_local_fast_path_enabled=True,
        intent_local_fast_path_threshold=0.82,
    )
    monkeypatch.setattr("app.services.intent_classifier.get_settings", lambda: settings)
    result = await analyze_intent("今天先这样，下次再聊", [])
    assert result.provider == "local"
    assert result.analysis.primary_intent == "end"
    assert result.analysis.confidence >= 0.82
