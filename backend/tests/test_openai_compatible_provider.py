import json
from collections.abc import AsyncIterator
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


def context() -> GenerationContext:
    return GenerationContext(
        persona_slug="confucius",
        persona_name="孔子",
        persona_manifest={},
        persona_style="先回应，再提问。",
        stage="CLARIFY",
        should_ask_question=True,
        user_text="我想换个角度看问题",
        skill_instructions=["保留整份 Skill 指令"],
    )


@pytest.mark.asyncio
async def test_stream_uses_large_budget_and_ignores_reasoning_in_user_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeAsyncClient.events = [
        {"choices": [{"delta": {"reasoning_content": "先分析问题"}}]},
        {"choices": [{"delta": {"content": "这是最终回答。"}}]},
        {"choices": [{"delta": {}, "finish_reason": "stop"}]},
    ]
    monkeypatch.setattr(
        "app.services.llm.openai_compatible.httpx.AsyncClient", FakeAsyncClient
    )
    provider = OpenAICompatibleProvider(
        Settings(llm_api_key="test-key", llm_base_url="https://example.test")
    )

    chunks = [chunk async for chunk in provider.stream(context())]

    assert chunks == ["这是最终回答。"]
    assert FakeAsyncClient.last_payload["max_tokens"] == 4096
    assert "保留整份 Skill 指令" in FakeAsyncClient.last_payload["messages"][0]["content"]


@pytest.mark.asyncio
async def test_reasoning_only_stream_reports_diagnostic_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeAsyncClient.events = [
        {"choices": [{"delta": {"reasoning_content": "只有思考"}}]},
        {"choices": [{"delta": {}, "finish_reason": "length"}]},
    ]
    monkeypatch.setattr(
        "app.services.llm.openai_compatible.httpx.AsyncClient", FakeAsyncClient
    )
    provider = OpenAICompatibleProvider(
        Settings(llm_api_key="test-key", llm_base_url="https://example.test")
    )

    with pytest.raises(EmptyModelContentError) as raised:
        _ = [chunk async for chunk in provider.stream(context())]

    assert raised.value.reasoning_chars == 4
    assert raised.value.finish_reason == "length"
