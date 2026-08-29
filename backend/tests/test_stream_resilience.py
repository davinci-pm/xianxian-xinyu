import asyncio
import json
from collections.abc import AsyncIterator

from app.api.v1.router import _stream_with_heartbeats


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
    return json.loads(raw)


async def test_stream_emits_heartbeats_during_slow_preparation_and_writing() -> None:
    async def slow_source() -> AsyncIterator[str]:
        await asyncio.sleep(0.025)
        yield 'event: meta\ndata: {"stage":"CLARIFY"}\n\n'
        yield 'event: chunk\ndata: {"text":"先"}\n\n'
        await asyncio.sleep(0.025)
        yield 'event: chunk\ndata: {"text":"贤"}\n\n'
        yield 'event: done\ndata: {"ok":true}\n\n'

    blocks = [
        block
        async for block in _stream_with_heartbeats(
            slow_source(), interval_seconds=0.01
        )
    ]
    heartbeats = [block for block in blocks if event_name(block) == "heartbeat"]

    assert [event_data(block)["phase"] for block in heartbeats] == [
        "preparing",
        "preparing",
        "writing",
        "writing",
    ]
    assert event_name(blocks[-1]) == "done"
