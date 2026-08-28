from enum import StrEnum
from typing import Any


class DialogueStage(StrEnum):
    BREAK_ICE = "BREAK_ICE"
    IDENTIFY_PROBLEM = "IDENTIFY_PROBLEM"
    CLARIFY = "CLARIFY"
    GUIDANCE = "GUIDANCE"
    REFLECTION = "REFLECTION"
    END = "END"
    SAFETY = "SAFETY"


END_MARKERS = ("先这样", "结束", "下次再聊", "谢谢不用了", "我想停下")


class ConversationDirector:
    def next_stage(
        self,
        current: str,
        user_text: str,
        question_streak: int,
        intent_analysis: dict[str, Any] | None = None,
    ) -> DialogueStage:
        if any(marker in user_text for marker in END_MARKERS):
            return DialogueStage.END
        try:
            stage = DialogueStage(current)
        except ValueError:
            stage = DialogueStage.IDENTIFY_PROBLEM
        if question_streak >= 2 and stage in {
            DialogueStage.IDENTIFY_PROBLEM,
            DialogueStage.CLARIFY,
        }:
            return DialogueStage.GUIDANCE
        if intent_analysis and float(intent_analysis.get("confidence", 0)) >= 0.8:
            recommended = str(intent_analysis.get("recommended_stage", ""))
            if recommended in {
                DialogueStage.CLARIFY,
                DialogueStage.GUIDANCE,
                DialogueStage.REFLECTION,
                DialogueStage.END,
            }:
                return DialogueStage(recommended)
        transitions = {
            DialogueStage.BREAK_ICE: DialogueStage.IDENTIFY_PROBLEM,
            DialogueStage.IDENTIFY_PROBLEM: DialogueStage.CLARIFY,
            DialogueStage.CLARIFY: DialogueStage.GUIDANCE,
            DialogueStage.GUIDANCE: DialogueStage.REFLECTION,
            DialogueStage.REFLECTION: DialogueStage.CLARIFY,
            DialogueStage.END: DialogueStage.END,
            DialogueStage.SAFETY: DialogueStage.SAFETY,
        }
        return transitions[stage]

    def should_ask_question(
        self,
        stage: DialogueStage,
        question_streak: int,
        intent_analysis: dict[str, Any] | None = None,
    ) -> bool:
        if intent_analysis is not None and not bool(
            intent_analysis.get("should_ask_question", True)
        ):
            return False
        return (
            stage
            in {
                DialogueStage.IDENTIFY_PROBLEM,
                DialogueStage.CLARIFY,
                DialogueStage.REFLECTION,
            }
            and question_streak < 2
        )


conversation_director = ConversationDirector()
