"""Per-IP limits for login and chat. In-app work is not limited."""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

_HITS: dict[str, deque] = defaultdict(deque)


def allow(key: str, limit: int, window_seconds: float = 60) -> bool:
    now = time.monotonic()
    bucket = _HITS[key]
    while bucket and now - bucket[0] > window_seconds:
        bucket.popleft()
    if len(bucket) >= limit:
        return False
    bucket.append(now)
    return True


def reset_limits() -> None:
    _HITS.clear()


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if os.getenv("DOGBUDDY_DISABLE_RATE_LIMIT") == "1":
            return await call_next(request)
        path = request.url.path
        if path.startswith("/auth"):
            limit = int(os.getenv("DOGBUDDY_AUTH_LIMIT", "30"))
            bucket = "auth"
        elif path == "/chat":
            limit = int(os.getenv("DOGBUDDY_CHAT_LIMIT", "20"))
            bucket = "chat"
        else:
            return await call_next(request)
        host = request.client.host if request.client else "unknown"
        if not allow(f"{host}:{bucket}", limit):
            return JSONResponse(
                {"detail": "Too many requests"},
                status_code=429,
            )
        return await call_next(request)
