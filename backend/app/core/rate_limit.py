from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from fastapi import HTTPException, status

from app.core.config import get_settings


class InMemoryRateLimiter:
    """适用于本地单进程纵向切片；生产环境需换成 Redis。"""

    def __init__(self) -> None:
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str) -> None:
        settings = get_settings()
        if not settings.rate_limit_enabled:
            return
        now = monotonic()
        cutoff = now - settings.rate_limit_window_seconds
        with self._lock:
            bucket = self._buckets[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= settings.rate_limit_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="请求有些频繁，请稍后再继续对话。",
                    headers={"Retry-After": str(settings.rate_limit_window_seconds)},
                )
            bucket.append(now)


rate_limiter = InMemoryRateLimiter()
