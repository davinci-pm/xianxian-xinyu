import json
import re
from dataclasses import dataclass
from time import monotonic
from typing import Literal, Protocol

import httpx
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings

IntentName = Literal[
    "decision",
    "emotional_support",
    "career",
    "relationship",
    "learning",
    "self_understanding",
    "casual",
    "end",
    "other",
]
EmotionName = Literal[
    "neutral",
    "confused",
    "anxious",
    "sad",
    "angry",
    "lonely",
    "hopeful",
]
DialogueMove = Literal["clarify", "reflect", "reframe", "challenge", "example", "action"]
RecommendedStage = Literal["IDENTIFY_PROBLEM", "CLARIFY", "GUIDANCE", "REFLECTION", "END"]


class IntentAnalysis(BaseModel):
    primary_intent: IntentName
    emotion: EmotionName
    user_need: str = Field(min_length=1, max_length=120)
    unresolved_issue: str = Field(min_length=1, max_length=200)
    recommended_move: DialogueMove
    recommended_stage: RecommendedStage
    should_ask_question: bool
    confidence: float = Field(ge=0, le=1)


@dataclass(frozen=True)
class IntentResult:
    analysis: IntentAnalysis
    provider: str
    model: str
    degraded: bool = False
    error_code: str | None = None
    latency_ms: int = 0


class IntentClassifier(Protocol):
    async def analyze(
        self, user_text: str, recent_messages: list[dict[str, str]]
    ) -> IntentResult: ...


class HeuristicIntentClassifier:
    async def analyze(self, user_text: str, recent_messages: list[dict[str, str]]) -> IntentResult:
        started = monotonic()
        del recent_messages
        text = user_text.strip()
        primary_intent: IntentName = "other"
        emotion: EmotionName = "neutral"
        move: DialogueMove = "clarify"
        stage: RecommendedStage = "CLARIFY"
        should_ask = True
        signal_count = 0

        if any(marker in text for marker in ("先这样", "结束", "下次再聊", "不聊了")):
            primary_intent = "end"
            move = "reflect"
            stage = "END"
            should_ask = False
            signal_count = 2
        elif any(marker in text for marker in ("工作", "职场", "老板", "辞职", "转行", "面试")):
            primary_intent = "career"
            signal_count += 1
        elif any(marker in text for marker in ("感情", "恋爱", "对象", "分手", "父母", "朋友")):
            primary_intent = "relationship"
            signal_count += 1
        elif any(marker in text for marker in ("选择", "决定", "要不要", "该不该", "两难")):
            primary_intent = "decision"
            signal_count += 1
        elif any(marker in text for marker in ("学习", "考试", "专业", "读书")):
            primary_intent = "learning"
            signal_count += 1
        elif any(marker in text for marker in ("难受", "低落", "压力", "崩溃", "痛苦")):
            primary_intent = "emotional_support"
            move = "reflect"
            signal_count += 1

        if any(marker in text for marker in ("焦虑", "担心", "害怕", "紧张")):
            emotion = "anxious"
        elif any(marker in text for marker in ("迷茫", "困惑", "不知道", "拿不准")):
            emotion = "confused"
        elif any(marker in text for marker in ("难过", "伤心", "低落", "痛苦")):
            emotion = "sad"
        elif any(marker in text for marker in ("生气", "愤怒", "气死")):
            emotion = "angry"
        elif any(marker in text for marker in ("孤独", "没人懂", "一个人")):
            emotion = "lonely"
        elif any(marker in text for marker in ("期待", "希望", "有信心")):
            emotion = "hopeful"
        if emotion != "neutral":
            signal_count += 1

        if stage != "END" and len(text) >= 48:
            stage = "GUIDANCE"
            move = "reframe"
            should_ask = False

        analysis = IntentAnalysis(
            primary_intent=primary_intent,
            emotion=emotion,
            user_need="理解用户真正想解决的问题",
            unresolved_issue=text[:200] or "用户尚未说明困惑",
            recommended_move=move,
            recommended_stage=stage,
            should_ask_question=should_ask,
            confidence=0.99 if primary_intent == "end" else min(0.48 + signal_count * 0.18, 0.9),
        )
        return IntentResult(
            analysis=analysis,
            provider="local",
            model="heuristic-intent-v1",
            latency_ms=int((monotonic() - started) * 1000),
        )


class OpenAICompatibleIntentClassifier:
    def __init__(self, settings: Settings) -> None:
        if not settings.intent_llm_api_key or not settings.intent_llm_base_url:
            raise RuntimeError("意图模型需要 INTENT_LLM_API_KEY 与 INTENT_LLM_BASE_URL")
        self._api_key = settings.intent_llm_api_key
        self._base_url = settings.intent_llm_base_url.rstrip("/")
        self._model = settings.intent_llm_model
        self._timeout = settings.intent_llm_timeout_seconds
        self._reasoning_effort = settings.intent_llm_reasoning_effort

    async def analyze(self, user_text: str, recent_messages: list[dict[str, str]]) -> IntentResult:
        started = monotonic()
        schema = IntentAnalysis.model_json_schema()
        payload: dict[str, object] = {
            "model": self._model,
            "stream": False,
            "temperature": 0.1,
            "max_tokens": 320,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "dialogue_intent", "strict": True, "schema": schema},
            },
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是主动型思想人格聊天产品的对话导演。分析用户真实意图、情绪和需要，"
                        "选择下一步对话动作。不要进行心理诊断，不要输出建议正文，只输出指定 JSON。"
                        "如果信息不足优先 CLARIFY；用户明确结束才选 END。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"recent_messages": recent_messages[-6:], "current_user_text": user_text},
                        ensure_ascii=False,
                    ),
                },
            ],
        }
        if self._reasoning_effort:
            payload["reasoning_effort"] = self._reasoning_effort
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/chat/completions", headers=headers, json=payload
            )
            response.raise_for_status()
        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("意图模型返回空内容")
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
        analysis = IntentAnalysis.model_validate_json(cleaned)
        return IntentResult(
            analysis=analysis,
            provider="openai_compatible",
            model=self._model,
            latency_ms=int((monotonic() - started) * 1000),
        )


async def analyze_intent(
    user_text: str, recent_messages: list[dict[str, str]]
) -> IntentResult:
    settings = get_settings()
    fallback = HeuristicIntentClassifier()
    fallback_result = await fallback.analyze(user_text, recent_messages)
    if not settings.intent_llm_enabled:
        return fallback_result
    if (
        settings.intent_local_fast_path_enabled
        and fallback_result.analysis.confidence >= settings.intent_local_fast_path_threshold
    ):
        return fallback_result
    started = monotonic()
    try:
        classifier = OpenAICompatibleIntentClassifier(settings)
        return await classifier.analyze(user_text, recent_messages)
    except Exception as exc:
        return IntentResult(
            analysis=fallback_result.analysis,
            provider=fallback_result.provider,
            model=fallback_result.model,
            degraded=True,
            error_code=type(exc).__name__,
            latency_ms=int((monotonic() - started) * 1000),
        )
