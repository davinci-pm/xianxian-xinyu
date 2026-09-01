import asyncio
import json
from collections.abc import AsyncIterator
from typing import cast

from app.api.v1.router import _retrieval_query, _stream_with_heartbeats


def event_name(block: str) -> str:
    return next(
        line.removeprefix("event:").strip()
        for line in block.splitlines()
        if line.startswith("event:")
    )


def event_data(block: str) -> dict[str, str]:
    raw = next(
        line.removeprefix("data:").strip()
        for line in block.splitlines()
        if line.startswith("data:")
    )
    return cast(dict[str, str], json.loads(raw))


async def test_stream_emits_heartbeats_during_slow_preparation_and_writing() -> None:
    async def slow_source() -> AsyncIterator[str]:
        await asyncio.sleep(0.025)
        yield 'event: meta\ndata: {"stage":"CLARIFY"}\n\n'
        yield 'event: chunk\ndata: {"text":"先"}\n\n'
        await asyncio.sleep(0.025)
        yield 'event: chunk\ndata: {"text":"贤"}\n\n'
        yield 'event: done\ndata: {"ok":true}\n\n'

    blocks = [
        block async for block in _stream_with_heartbeats(slow_source(), interval_seconds=0.01)
    ]
    heartbeats = [block for block in blocks if event_name(block) == "heartbeat"]

    assert [event_data(block)["phase"] for block in heartbeats] == [
        "preparing",
        "preparing",
        "writing",
        "writing",
    ]
    assert event_name(blocks[-1]) == "done"


def test_short_followup_retrieval_restores_subject_but_vague_opening_does_not() -> None:
    recent = [
        {"role": "user", "content": "我在考虑要不要离职去做自己的产品"},
        {"role": "assistant", "content": "先看你能承担多大的试错成本。"},
    ]

    restored = _retrieval_query("为什么？", recent)
    assert "离职" in restored
    assert restored.endswith("为什么？")
    assert _retrieval_query("为什么", []) == ""


def test_retrieval_skips_clear_small_talk_but_keeps_short_meaningful_topics() -> None:
    recent = [{"role": "user", "content": "我在考虑要不要离职"}]

    assert _retrieval_query("哈哈哈哈", recent) == ""
    assert _retrieval_query("你好", recent) == ""
    assert "内耗" in _retrieval_query("内耗", [])


def test_origin_question_expands_retrieval_toward_direct_early_evidence() -> None:
    query = _retrieval_query("你为什么进入加密行业？为什么后来做 TRON？", [])

    assert "最初" in query
    assert "动机" in query
    assert "创立" in query
    assert "inspiration" in query
