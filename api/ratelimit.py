import logging
import time
from collections import defaultdict

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple in-memory sliding window rate limiter."""

    def __init__(self, requests_per_minute: int = 60):
        self.rpm = requests_per_minute
        self._windows: dict[str, list[float]] = defaultdict(list)

    def _get_client_id(self, request: Request) -> str:
        """Get client identifier from API key header or IP."""
        api_key = request.headers.get("X-API-Key", "")
        if api_key:
            return f"key:{api_key[:16]}"
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"
        return f"ip:{request.client.host if request.client else 'unknown'}"

    def check(self, request: Request) -> None:
        """Check rate limit. Raises HTTPException(429) if exceeded."""
        client_id = self._get_client_id(request)
        now = time.time()
        window_start = now - 60.0

        # Clean old entries
        timestamps = self._windows[client_id]
        self._windows[client_id] = [t for t in timestamps if t > window_start]

        if len(self._windows[client_id]) >= self.rpm:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded ({self.rpm} requests/minute)",
                headers={"Retry-After": "60"},
            )

        self._windows[client_id].append(now)


rate_limiter = RateLimiter(requests_per_minute=120)
