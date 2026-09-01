from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import User, VisitorSession
from app.services.auth import decode_session_cookie


@dataclass(frozen=True)
class VisitorIdentity:
    visitor: VisitorSession
    user: User | None
    cookie_created: bool

    @property
    def authenticated(self) -> bool:
        return self.user is not None


def resolve_visitor(
    request: Request,
    db: Session,
    *,
    require_auth: bool | None = None,
) -> VisitorIdentity:
    settings = get_settings()
    visitor_id = decode_session_cookie(request.cookies.get(settings.cookie_name))
    visitor = db.get(VisitorSession, visitor_id) if visitor_id else None
    if visitor is None:
        visitor = VisitorSession(locale="zh-CN")
        db.add(visitor)
        db.flush()
        cookie_created = True
    else:
        cookie_created = False
    user = db.get(User, visitor.user_id) if visitor.user_id else None
    should_require_auth = settings.auth_required if require_auth is None else require_auth
    if should_require_auth and user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先使用邀请码登录")
    visitor.last_seen_at = datetime.now(UTC)
    db.commit()
    return VisitorIdentity(visitor=visitor, user=user, cookie_created=cookie_created)
