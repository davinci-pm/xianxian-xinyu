import json
from collections.abc import AsyncIterator
from dataclasses import replace
from typing import Any

import pytest

from app.core.config import Settings
from app.services.llm.base import GenerationContext
from app.services.llm.openai_compatible import (
    EmptyModelContentError,
    OpenAICompatibleProvider,
)


class FakeStreamResponse:
    def __init__(self, events: list[dict[str, Any]]) -> None:
        self.events = events

    async def __aenter__(self) -> "FakeStreamResponse":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    async def aiter_lines(self) -> AsyncIterator[str]:
        for event in self.events:
            yield f"data: {json.dumps(event, ensure_ascii=False)}"
        yield "data: [DONE]"


class FakeAsyncClient:
    last_payload: dict[str, Any] = {}
    events: list[dict[str, Any]] = []

    def __init__(self, **_kwargs: object) -> None:
        pass

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    def stream(self, _method: str, _url: str, **kwargs: Any) -> FakeStreamResponse:
        self.__class__.last_payload = kwargs["json"]
        return FakeStreamResponse(self.__class__.events)


def context(
    user_text: str = "我想换个角度看问题",
    *,
    intent: str = "other",
    stage: str = "CLARIFY",
    move: str = "clarify",
) -> GenerationContext:
    return GenerationContext(
        persona_slug="confucius",
        persona_name="孔子",
        persona_manifest={},
        persona_style="先回应，再提问。",
        stage=stage,
        should_ask_question=True,
        user_text=user_text,
        skill_instructions=["保留整份 Skill 指令"],
        intent_analysis={"primary_intent": intent, "recommended_move": move},
    )


@pytest.mark.asyncio
async def test_stream_uses_fast_budget_and_ignores_reasoning_in_user_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeAsyncClient.events = [
        {"choices": [{"delta": {"reasoning_content": "先分析问题"}}]},
        {"choices": [{"delta": {"content": "这是最终回答。"}}]},
        {"choices": [{"delta": {}, "finish_reason": "stop"}]},
    ]
    monkeypatch.setattr("app.services.llm.openai_compatible.httpx.AsyncClient", FakeAsyncClient)
    provider = OpenAICompatibleProvider(
        Settings(llm_api_key="test-key", llm_base_url="https://example.test")
    )

    chunks = [chunk async for chunk in provider.stream(context())]

    assert chunks == ["这是最终回答。"]
    assert FakeAsyncClient.last_payload["max_tokens"] == 1200
    system_prompt = FakeAsyncClient.last_payload["messages"][0]["content"]
    turn_prompt = FakeAsyncClient.last_payload["messages"][-1]["content"]
    assert "保留整份 Skill 指令" in turn_prompt
    assert "这一条优先于人物方法中的反问习惯" in turn_prompt
    assert "直接以人物第一人称说话" in system_prompt
    assert "不要自称AI、助手或模型" in system_prompt
    assert "只有用户明确询问现实身份、真伪或授权时" in system_prompt
    assert "每轮只选一个最有辨识度的人物原则" in system_prompt
    assert "检索片段只是候选证据" in system_prompt
    assert "反问也计入本轮问句数" in system_prompt


@pytest.mark.asyncio
async def test_deepseek_adaptive_thinking_is_disabled_for_normal_chat_and_enabled_for_complex_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeAsyncClient.events = [
        {"choices": [{"delta": {"content": "回答"}}]},
        {"choices": [{"delta": {}, "finish_reason": "stop"}]},
    ]
    monkeypatch.setattr("app.services.llm.openai_compatible.httpx.AsyncClient", FakeAsyncClient)
    provider = OpenAICompatibleProvider(
        Settings(llm_api_key="test-key", llm_base_url="https://api.deepseek.com")
    )

    _ = [chunk async for chunk in provider.stream(context("我今天很迷茫"))]
    assert FakeAsyncClient.last_payload["thinking"] == {"type": "disabled"}
    assert FakeAsyncClient.last_payload["max_tokens"] == 1200

    complex_text = "请系统分析和比较这两个长期职业方案的利弊、风险和可逆性，" * 3
    _ = [chunk async for chunk in provider.stream(context(complex_text))]
    assert FakeAsyncClient.last_payload["thinking"] == {"type": "enabled"}
    assert FakeAsyncClient.last_payload["reasoning_effort"] == "low"
    assert FakeAsyncClient.last_payload["max_tokens"] == 2048

    _ = [
        chunk
        async for chunk in provider.stream(
            context(
                "你为什么进入加密行业？为什么后来做 TRON？",
                intent="learning",
                stage="GUIDANCE",
                move="example",
            )
        )
    ]
    assert FakeAsyncClient.last_payload["thinking"] == {"type": "disabled"}


@pytest.mark.asyncio
async def test_adaptive_thinking_uses_semantics_without_slowing_emotional_support(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeAsyncClient.events = [{"choices": [{"delta": {"content": "回答"}}]}]
    monkeypatch.setattr("app.services.llm.openai_compatible.httpx.AsyncClient", FakeAsyncClient)
    provider = OpenAICompatibleProvider(
        Settings(llm_api_key="test-key", llm_base_url="https://api.deepseek.com")
    )

    _ = [
        chunk
        async for chunk in provider.stream(
            context("人生的意义为什么要自己创造？", intent="self_understanding")
        )
    ]
    assert FakeAsyncClient.last_payload["thinking"] == {"type": "enabled"}

    _ = [
        chunk
        async for chunk in provider.stream(
            context("我今天真的很难过，什么都不想做", intent="emotional_support")
        )
    ]
    assert FakeAsyncClient.last_payload["thinking"] == {"type": "disabled"}


@pytest.mark.asyncio
async def test_reasoning_only_stream_reports_diagnostic_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeAsyncClient.events = [
        {"choices": [{"delta": {"reasoning_content": "只有思考"}}]},
        {"choices": [{"delta": {}, "finish_reason": "length"}]},
    ]
    monkeypatch.setattr("app.services.llm.openai_compatible.httpx.AsyncClient", FakeAsyncClient)
    provider = OpenAICompatibleProvider(
        Settings(llm_api_key="test-key", llm_base_url="https://example.test")
    )

    with pytest.raises(EmptyModelContentError) as raised:
        _ = [chunk async for chunk in provider.stream(context())]

    assert raised.value.reasoning_chars == 4
    assert raised.value.finish_reason == "length"


@pytest.mark.asyncio
async def test_created_persona_prompt_requires_evidence_for_biographical_claims(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeAsyncClient.events = [{"choices": [{"delta": {"content": "回答"}}]}]
    monkeypatch.setattr("app.services.llm.openai_compatible.httpx.AsyncClient", FakeAsyncClient)
    provider = OpenAICompatibleProvider(
        Settings(llm_api_key="test-key", llm_base_url="https://api.deepseek.com")
    )
    created = replace(
        context(),
        persona_slug="created-test-persona",
        persona_manifest={
            "cognitive_model": {
                "value_hierarchy": [{"value": "长期主义", "priority": 1}],
                "conditional_rules": [{"condition": "短期与长期冲突"}],
            }
        },
        generation_plan={
            "mode": "mixed",
            "answer_policy": "先回答事实，再标记框架推演。",
            "activated_persona_assets": {
                "value_hierarchy": [{"value": "长期主义", "priority": 1}],
            },
            "review_checklist": ["不得把推演写成经历"],
        },
    )

    _ = [chunk async for chunk in provider.stream(created)]

    system_prompt = FakeAsyncClient.last_payload["messages"][0]["content"]
    assert "不能用当前原则倒推出过去动机" in system_prompt
    assert "资料未提供的内部过程" in system_prompt
    assert "这批资料没有直接说明当时动机" in system_prompt
    assert "我早期也经历过" in system_prompt
    assert "长期主义" in system_prompt
    assert "本轮激活的人格证据" in system_prompt
    assert "认知模型" not in system_prompt
    assert "只输出复核后的最终回答" in system_prompt
    assert "generation_plan" in FakeAsyncClient.last_payload["messages"][-1]["content"]
    assert "先回答事实" in FakeAsyncClient.last_payload["messages"][-1]["content"]
