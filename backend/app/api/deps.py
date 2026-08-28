from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import VisitorSession


@dataclass(frozen=True)
class VisitorIdentity:
    visitor: VisitorSession
    cookie_created: bool


def resolve_visitor(request: Request, db: Session) -> VisitorIdentity:
    cookie_value = request.cookies.get(get_settings().cookie_name)
    visitor = db.get(VisitorSession, cookie_value) if cookie_value else None
    if visitor is None:
        visitor = VisitorSession(locale="zh-CN")
        db.add(visitor)
        db.flush()
        cookie_created = True
    else:
        cookie_created = False
    visitor.last_seen_at = datetime.now(UTC)
    db.commit()
    return VisitorIdentity(visitor=visitor, cookie_created=cookie_created)
