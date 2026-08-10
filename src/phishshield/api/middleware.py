"""Lightweight, dependency-free middleware for the demo API: a bounded
per-IP request-rate limiter and a request-body size cap.

Both are in-process, in-memory implementations -- adequate for a single
small instance (this project's actual deployment target), not for a
multi-instance production fleet (that would need a shared store like
Redis). Documented as a known scope limit rather than silently pretended
to be more robust than it is.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from phishshield.api import config


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window-ish limiter: at most `requests_per_minute` requests
    per client IP in any trailing 60-second window. Exempts `/health` so
    monitoring/uptime checks are never throttled.
    """

    def __init__(self, app, requests_per_minute: int = config.RATE_LIMIT_PER_MINUTE):
        super().__init__(app)
        self.limit = requests_per_minute
        self._hits: dict[str, deque] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/health":
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window = self._hits[client_ip]
        while window and now - window[0] > 60:
            window.popleft()

        if len(window) >= self.limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "rate limit exceeded, try again shortly"},
            )

        window.append(now)
        return await call_next(request)


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """Rejects requests whose declared Content-Length exceeds
    `max_bytes` before the body is ever read into memory -- the feature
    dict this API expects is always small (a few dozen numeric fields);
    there is never a legitimate reason for a large payload here.
    """

    def __init__(self, app, max_bytes: int = config.MAX_REQUEST_BYTES):
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                size = int(content_length)
            except ValueError:
                size = None
            if size is not None and size > self.max_bytes:
                return JSONResponse(
                    status_code=413,
                    content={"detail": f"request body exceeds {self.max_bytes} bytes"},
                )
        return await call_next(request)
