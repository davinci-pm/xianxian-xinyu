import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Memory, Message

SENSITIVE_TERMS = (
    "身份证",
    "银行卡",
    "密码",
    "住址",
    "自杀",
    "自残",
    "诊断",
    "病历",
)
MEMORY_PATTERN = re.compile(r"我(想|希望|正在|准备|打算)([^。！？\n]{2,100})")


def extract_memory_candidate(
    db: Session,
    *,
    visitor_id: str,
    persona_id: str,
    conversation_id: str,
    message: Message,
) -> Memory | None:
    if any(term in message.content for term in SENSITIVE_TERMS):
        return None
    match = MEMORY_PATTERN.search(message.content)
    if not match:
        return None
    content = f"用户{match.group(1)}{match.group(2).strip()}"
    candidate = Memory(
        visitor_id=visitor_id,
        persona_id=persona_id,
        conversation_id=conversation_id,
        kind="goal_or_unresolved_issue",
        content=content[:500],
        scope="candidate",
        status="pending",
        confidence=78,
        source_message_id=message.id,
    )
    db.add(candidate)
    db.flush()
    return candidate


def list_confirmed_memories(
    db: Session, visitor_id: str, persona_id: str, limit: int = 5
) -> list[Memory]:
    statement = (
        select(Memory)
        .where(
            Memory.visitor_id == visitor_id,
            Memory.persona_id == persona_id,
            Memory.scope == "long_term",
            Memory.status == "confirmed",
        )
        .order_by(Memory.confirmed_at.desc())
        .limit(limit)
    )
    return list(db.scalars(statement))


def confirm_memory(memory: Memory, action: str, edited_content: str | None) -> Memory:
    if edited_content:
        memory.content = edited_content.strip()
    if action == "remember":
        memory.scope = "long_term"
        memory.status = "confirmed"
        memory.confirmed_at = datetime.now(UTC)
    elif action == "session_only":
        memory.scope = "session"
        memory.status = "confirmed"
        memory.confirmed_at = datetime.now(UTC)
    else:
        memory.scope = "discarded"
        memory.status = "rejected"
    return memory
