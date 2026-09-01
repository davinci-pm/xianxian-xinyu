from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

_INLINE_PATTERNS = (
    re.compile(
        r"^\s*\[?(?P<time>20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2}日?\s+\d{1,2}:\d{2}(?::\d{2})?)\]?\s+"
        r"(?P<speaker>[^:：]{1,40})[:：]\s*(?P<content>.+?)\s*$"
    ),
    re.compile(
        r"^\s*(?P<speaker>[^:：]{1,40})\s+"
        r"(?P<time>20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2}日?\s+\d{1,2}:\d{2}(?::\d{2})?)"
        r"[:：]?\s*(?P<content>.+?)\s*$"
    ),
)
_HEADER_RE = re.compile(
    r"^\s*(?P<time>20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2}日?\s+\d{1,2}:\d{2}(?::\d{2})?)\s+"
    r"(?P<speaker>.{1,40}?)\s*$"
)
_SIMPLE_RE = re.compile(r"^\s*(?P<speaker>[^:：]{1,40})[:：]\s*(?P<content>.+?)\s*$")
_SYSTEM_MARKERS = (
    "撤回了一条消息",
    "领取了你的红包",
    "你领取了",
    "以下为新消息",
    "加入了群聊",
    "修改群名为",
    "拍了拍",
)
_LOW_INFORMATION = re.compile(
    r"^(?:嗯+|哦+|哈+|好+|行+|收到|可以|ok|1|在|[？?。.])(?:[!！？?。.])*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ChatTurn:
    speaker: str
    content: str
    timestamp: str | None
    context_before: str | None
    session_index: int

    def as_dict(self) -> dict[str, str | int | None]:
        return asdict(self)


def _normalize_speaker(value: str) -> str:
    return re.sub(r"[\s@（）()\[\]]", "", value).lower()


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = (
        value.replace("年", "-")
        .replace("月", "-")
        .replace("日", "")
        .replace("/", "-")
        .replace(".", "-")
    )
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(normalized, pattern)
        except ValueError:
            continue
    return None


def _valid_content(value: str) -> bool:
    return bool(value.strip()) and not any(marker in value for marker in _SYSTEM_MARKERS)


def parse_chat_turns(content: str) -> list[ChatTurn]:
    raw: list[tuple[str, str, str | None]] = []
    pending_header: tuple[str, str] | None = None
    for raw_line in content.replace("\x00", "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        inline = next(
            (match for pattern in _INLINE_PATTERNS if (match := pattern.match(line))),
            None,
        )
        if inline:
            value = inline.group("content").strip()
            if _valid_content(value):
                raw.append((inline.group("speaker").strip(), value, inline.group("time")))
            pending_header = None
            continue
        header = _HEADER_RE.match(line)
        if header:
            pending_header = (header.group("speaker").strip(), header.group("time"))
            continue
        if pending_header:
            if _valid_content(line):
                raw.append((pending_header[0], line, pending_header[1]))
            pending_header = None
            continue
        simple = _SIMPLE_RE.match(line)
        if simple:
            value = simple.group("content").strip()
            if _valid_content(value):
                raw.append((simple.group("speaker").strip(), value, None))

    turns: list[ChatTurn] = []
    previous_time: datetime | None = None
    previous_content: str | None = None
    session_index = 0
    for speaker, value, timestamp in raw:
        parsed_time = _parse_time(timestamp)
        if parsed_time and previous_time and (parsed_time - previous_time).total_seconds() > 3600:
            session_index += 1
            previous_content = None
        turns.append(
            ChatTurn(
                speaker=speaker,
                content=value,
                timestamp=parsed_time.isoformat() if parsed_time else timestamp,
                context_before=previous_content,
                session_index=session_index,
            )
        )
        previous_time = parsed_time or previous_time
        previous_content = value
    return turns


def extract_target_messages(content: str, target_speaker: str) -> str:
    turns = parse_chat_turns(content)
    if not turns:
        return content.strip()
    target = _normalize_speaker(target_speaker)
    selected = [turn.content for turn in turns if _normalize_speaker(turn.speaker) == target]
    return "\n".join(selected)


def analyze_chat_quality(content: str, target_speaker: str | None) -> dict[str, Any]:
    turns = parse_chat_turns(content)
    speakers = {_normalize_speaker(turn.speaker) for turn in turns}
    target = _normalize_speaker(target_speaker or "")
    target_turns = [turn for turn in turns if target and _normalize_speaker(turn.speaker) == target]
    substantive = [
        turn
        for turn in target_turns
        if len(turn.content) >= 12 and not _LOW_INFORMATION.match(turn.content)
    ]
    dated = [_parse_time(turn.timestamp) for turn in turns if turn.timestamp]
    valid_dates = [value for value in dated if value is not None]
    temporal_days = (
        max(0, (max(valid_dates) - min(valid_dates)).days) if len(valid_dates) >= 2 else 0
    )
    return {
        "parsed_turns": len(turns),
        "target_turns": len(target_turns),
        "speaker_count": len(speakers),
        "counterpart_count": max(0, len(speakers - ({target} if target else set()))),
        "session_count": len({turn.session_index for turn in turns}),
        "temporal_span_days": temporal_days,
        "substantive_target_turns": len(substantive),
        "substantive_ratio": round(len(substantive) / max(len(target_turns), 1), 3),
        "speaker_purity": round(len(target_turns) / max(len(turns), 1), 3),
        "context_available_ratio": round(
            sum(bool(turn.context_before) for turn in target_turns) / max(len(target_turns), 1), 3
        ),
    }
