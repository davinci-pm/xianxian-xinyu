import hashlib
import hmac
from dataclasses import dataclass

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Conversation, Memory, User, VisitorSession


@dataclass(frozen=True)
class InviteMatch:
    user_id: str
    account_key: str
    display_name: str


def configured_invite_codes() -> list[str]:
    return [code.strip() for code in get_settings().invite_codes.split(",") if code.strip()]


def match_invite_code(candidate: str) -> InviteMatch | None:
    submitted = candidate.strip()
    settings = get_settings()
    for index, configured in enumerate(configured_invite_codes(), start=1):
        if not hmac.compare_digest(submitted, configured):
            continue
        digest = hmac.new(
            settings.session_secret.encode(),
            configured.encode(),
            hashlib.sha256,
        ).hexdigest()
        return InviteMatch(
            user_id=digest[:32],
            account_key=f"invite-{digest[:24]}@users.sage.local",
            display_name=f"内测用户 {index:02d}",
        )
    return None


def get_or_create_invite_user(db: Session, match: InviteMatch) -> User:
    user = db.get(User, match.user_id)
    if user is None:
        user = User(
            id=match.user_id,
            email=match.account_key,
            display_name=match.display_name,
            locale="zh-CN",
            long_memory_enabled=True,
        )
        db.add(user)
        db.flush()
    elif user.display_name != match.display_name:
        user.display_name = match.display_name
    return user


def attach_visitor_to_user(db: Session, visitor: VisitorSession, user: User) -> None:
    visitor.user_id = user.id
    db.execute(
        update(Conversation)
        .where(Conversation.visitor_id == visitor.id, Conversation.user_id.is_(None))
        .values(user_id=user.id)
    )
    db.execute(
        update(Memory)
        .where(Memory.visitor_id == visitor.id, Memory.user_id.is_(None))
        .values(user_id=user.id)
    )


def encode_session_cookie(visitor_id: str) -> str:
    signature = hmac.new(
        get_settings().session_secret.encode(), visitor_id.encode(), hashlib.sha256
    ).hexdigest()
    return f"{visitor_id}.{signature}"


def decode_session_cookie(value: str | None) -> str | None:
    if not value or "." not in value:
        return None
    visitor_id, signature = value.rsplit(".", 1)
    if len(visitor_id) != 32:
        return None
    expected = hmac.new(
        get_settings().session_secret.encode(), visitor_id.encode(), hashlib.sha256
    ).hexdigest()
    return visitor_id if hmac.compare_digest(signature, expected) else None
