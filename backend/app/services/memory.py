from datetime import UTC, datetime

from sqlalchemy import and_, or_, select
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
ALLOWED_MEMORY_KINDS = {
    "preference",
    "personal_context",
    "goal",
    "unresolved_issue",
    "decision",
}


def create_memory_candidate(
    db: Session,
    *,
    visitor_id: str,
    user_id: str | None,
    persona_id: str,
    conversation_id: str,
    message: Message,
    should_offer: bool,
    kind: str,
    content: str,
    confidence: float,
) -> Memory | None:
    cleaned = content.strip()
    if (
        not should_offer
        or kind not in ALLOWED_MEMORY_KINDS
        or confidence < 0.72
        or not cleaned
        or any(term in cleaned for term in SENSITIVE_TERMS)
    ):
        return None
    owner_filter = Memory.user_id == user_id if user_id else Memory.visitor_id == visitor_id
    duplicate = db.scalar(
        select(Memory.id).where(
            owner_filter,
            Memory.persona_id == persona_id,
            Memory.content == cleaned[:500],
            Memory.status.in_(("pending", "confirmed", "paused")),
        )
    )
    if duplicate is not None:
        return None
    candidate = Memory(
        visitor_id=visitor_id,
        user_id=user_id,
        persona_id=persona_id,
        conversation_id=conversation_id,
        kind=kind,
        content=cleaned[:500],
        scope="candidate",
        status="pending",
        confidence=round(confidence * 100),
        source_message_id=message.id,
    )
    db.add(candidate)
    db.flush()
    return candidate


def list_confirmed_memories(
    db: Session,
    visitor_id: str,
    persona_id: str,
    limit: int = 5,
    *,
    user_id: str | None = None,
    conversation_id: str | None = None,
) -> list[Memory]:
    owner_filter = Memory.user_id == user_id if user_id else Memory.visitor_id == visitor_id
    scope_filter = Memory.scope == "long_term"
    if conversation_id:
        scope_filter = or_(
            Memory.scope == "long_term",
            and_(
                Memory.scope == "session",
                Memory.conversation_id == conversation_id,
            ),
        )
    statement = (
        select(Memory)
        .where(
            owner_filter,
            Memory.persona_id == persona_id,
            scope_filter,
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
