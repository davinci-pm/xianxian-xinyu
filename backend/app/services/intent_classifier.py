import json
import re
from dataclasses import dataclass
from time import monotonic
from typing import Literal, Protocol

import httpx
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.services.dialogue_signals import is_explicit_end

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
MemoryKind = Literal[
    "none",
    "preference",
    "personal_context",
    "goal",
    "unresolved_issue",
    "decision",
]


class IntentAnalysis(BaseModel):
    primary_intent: IntentName
    emotion: EmotionName
    user_need: str = Field(min_length=1, max_length=120)
    unresolved_issue: str = Field(min_length=1, max_length=200)
    recommended_move: DialogueMove
    recommended_stage: RecommendedStage
    should_ask_question: bool
    confidence: float = Field(ge=0, le=1)
    memory_should_offer: bool
    memory_kind: MemoryKind
    memory_content: str = Field(max_length=160)
    memory_confidence: float = Field(ge=0, le=1)


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

        if is_explicit_end(text):
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

        direct_request = any(
            marker in text
            for marker in (
                "怎么",
                "该不该",
                "要不要",
                "为什么",
                "问题在哪",
                "先抓什么",
                "怎么选",
                "怎么做",
            )
        )
        has_specific_context = len(text) >= 18 and any(
            marker in text
            for marker in (
                "我",
                "产品",
                "工作",
                "公司",
                "团队",
                "父母",
                "家人",
                "学习",
                "公式",
            )
        )
        if stage != "END" and (len(text) >= 48 or (direct_request and has_specific_context)):
            stage = "GUIDANCE"
            move = (
                "reflect"
                if primary_intent == "emotional_support"
                else "example"
                if primary_intent == "learning"
                else "action"
                if primary_intent in {"career", "decision"}
                else "reframe"
            )
            should_ask = False

        memory_should_offer = False
        memory_kind: MemoryKind = "none"
        memory_content = ""
        memory_confidence = 0.0
        sensitive = any(
            marker in text
            for marker in ("身份证", "银行卡", "密码", "住址", "病历", "诊断", "自杀", "自残")
        )
        asks_assistant = any(marker in text for marker in ("我希望你", "我想让你", "我想问你"))
        memory_patterns: tuple[tuple[MemoryKind, tuple[str, ...]], ...] = (
            ("decision", ("我决定", "我已经决定", "我最终选择")),
            ("preference", ("我喜欢", "我不喜欢", "我的偏好", "我习惯")),
            (
                "goal",
                ("我的目标", "我计划", "我准备", "我打算", "我希望", "我想辞职", "我想转行"),
            ),
            ("personal_context", ("我的工作是", "我在做", "我是一个", "我目前在")),
            ("unresolved_issue", ("我一直困扰", "我长期", "我总是")),
        )
        if not sensitive and not asks_assistant:
            for candidate_kind, markers in memory_patterns:
                if any(marker in text for marker in markers):
                    memory_should_offer = True
                    memory_kind = candidate_kind
                    memory_content = text[:160]
                    memory_confidence = 0.82
                    break

        analysis = IntentAnalysis(
            primary_intent=primary_intent,
            emotion=emotion,
            user_need="理解用户真正想解决的问题",
            unresolved_issue=text[:200] or "用户尚未说明困惑",
            recommended_move=move,
            recommended_stage=stage,
            should_ask_question=should_ask,
            confidence=0.99 if primary_intent == "end" else min(0.48 + signal_count * 0.18, 0.9),
            memory_should_offer=memory_should_offer,
            memory_kind=memory_kind,
            memory_content=memory_content,
            memory_confidence=memory_confidence,
        )
        return IntentResult(
            analysis=analysis,
            provider="local",
            model="heuristic-intent-v1",
            latency_ms=int((monotonic() - started) * 1000),
        )


class OpenAICompatibleIntentClassifier:
    def __init__(self, settings: Settings) -> None:
        has_dedicated_intent_model = bool(
            settings.intent_llm_api_key and settings.intent_llm_base_url
        )
        self._api_key = (
            settings.intent_llm_api_key if has_dedicated_intent_model else settings.llm_api_key
        )
        base_url = (
            settings.intent_llm_base_url if has_dedicated_intent_model else settings.llm_base_url
        )
        if not self._api_key or not base_url:
            raise RuntimeError("语义分析需要独立意图模型或主模型配置")
        self._base_url = base_url.rstrip("/")
        self._model = (
            settings.intent_llm_model if has_dedicated_intent_model else settings.llm_model
        )
        self._timeout = settings.intent_llm_timeout_seconds if has_dedicated_intent_model else 4.0
        self._reasoning_effort = (
            settings.intent_llm_reasoning_effort if has_dedicated_intent_model else None
        )

    async def analyze(self, user_text: str, recent_messages: list[dict[str, str]]) -> IntentResult:
        started = monotonic()
        schema = IntentAnalysis.model_json_schema()
        schema_text = json.dumps(schema, ensure_ascii=False)
        is_deepseek = "api.deepseek.com" in self._base_url
        payload: dict[str, object] = {
            "model": self._model,
            "stream": False,
            "temperature": 0.1,
            "max_tokens": 480,
            "response_format": (
                {"type": "json_object"}
                if is_deepseek
                else {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "dialogue_intent",
                        "strict": True,
                        "schema": schema,
                    },
                }
            ),
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是主动型思想人格聊天产品的对话导演。分析用户真实意图、情绪和需要，"
                        "选择下一步对话动作。不要进行心理诊断，不要输出建议正文，只输出指定 JSON。"
                        "如果信息不足优先 CLARIFY；用户明确结束才选 END。"
                        "同时保守判断本轮是否包含值得当前人物跨会话记住的重要信息。"
                        "只有可能持续至少数周、且会明显改善未来对话的稳定偏好、个人背景、长期目标、"
                        "未解决问题或明确决定，memory_should_offer 才为 true；临时情绪、普通闲聊、"
                        "对助手的要求、重复信息和敏感信息必须为 false。"
                        "memory_content 要独立、简短、忠于用户原意，不添加推测；"
                        "不需要记忆时内容为空、kind 为 none、置信度为 0。"
                        f"只输出符合以下 JSON Schema 的 JSON：{schema_text}"
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
        if is_deepseek:
            payload["thinking"] = {"type": "disabled"}
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


async def analyze_intent(user_text: str, recent_messages: list[dict[str, str]]) -> IntentResult:
    settings = get_settings()
    fallback = HeuristicIntentClassifier()
    fallback_result = await fallback.analyze(user_text, recent_messages)
    if not settings.intent_llm_enabled:
        return fallback_result
    if (
        settings.intent_local_fast_path_enabled
        and fallback_result.analysis.confidence >= settings.intent_local_fast_path_threshold
        and fallback_result.analysis.primary_intent == "end"
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
