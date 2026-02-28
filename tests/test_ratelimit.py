"""
Tests for api/ratelimit.py -- sliding window rate limiting.

All HTTP/Request objects are mocked.
"""

import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from api.ratelimit import RateLimiter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(
    api_key: str | None = None,
    forwarded_for: str | None = None,
    client_host: str = "127.0.0.1",
    has_client: bool = True,
) -> MagicMock:
    """Create a mock FastAPI Request object."""
    request = MagicMock()

    headers = {}
    if api_key:
        headers["X-API-Key"] = api_key
    if forwarded_for:
        headers["X-Forwarded-For"] = forwarded_for

    request.headers = headers

    if has_client:
        request.client = MagicMock()
        request.client.host = client_host
    else:
        request.client = None

    return request


# ---------------------------------------------------------------------------
# _get_client_id
# ---------------------------------------------------------------------------


class TestGetClientId:
    """_get_client_id should identify clients by API key, forwarded IP, or host."""

    def test_uses_api_key_when_present(self):
        """Should use the API key (truncated to 16 chars) as client identifier."""
        limiter = RateLimiter(requests_per_minute=60)
        request = _make_request(api_key="lnc_abcdefghijklmnopqrstuvwxyz1234")
        client_id = limiter._get_client_id(request)
        assert client_id == "key:lnc_abcdefghijkl"

    def test_uses_forwarded_for_when_no_api_key(self):
        """Should use X-Forwarded-For IP when no API key is present."""
        limiter = RateLimiter(requests_per_minute=60)
        request = _make_request(forwarded_for="10.0.0.1, 192.168.1.1")
        client_id = limiter._get_client_id(request)
        assert client_id == "ip:10.0.0.1"

    def test_forwarded_for_single_ip(self):
        """Should handle a single IP in X-Forwarded-For."""
        limiter = RateLimiter(requests_per_minute=60)
        request = _make_request(forwarded_for="203.0.113.50")
        client_id = limiter._get_client_id(request)
        assert client_id == "ip:203.0.113.50"

    def test_falls_back_to_client_host(self):
        """Should use client.host when no API key or forwarded header exists."""
        limiter = RateLimiter(requests_per_minute=60)
        request = _make_request(client_host="192.168.1.100")
        client_id = limiter._get_client_id(request)
        assert client_id == "ip:192.168.1.100"

    def test_handles_missing_client(self):
        """Should return 'ip:unknown' when request.client is None."""
        limiter = RateLimiter(requests_per_minute=60)
        request = _make_request(has_client=False)
        client_id = limiter._get_client_id(request)
        assert client_id == "ip:unknown"

    def test_api_key_takes_priority(self):
        """API key should take priority over X-Forwarded-For."""
        limiter = RateLimiter(requests_per_minute=60)
        request = _make_request(
            api_key="lnc_my_api_key_here_1234",
            forwarded_for="10.0.0.1",
        )
        client_id = limiter._get_client_id(request)
        assert client_id.startswith("key:")


# ---------------------------------------------------------------------------
# RateLimiter.check
# ---------------------------------------------------------------------------


class TestRateLimiterCheck:
    """RateLimiter.check should enforce sliding-window rate limits."""

    def test_allows_requests_within_limit(self):
        """Requests under the limit should pass without raising."""
        limiter = RateLimiter(requests_per_minute=5)
        request = _make_request(client_host="10.0.0.1")

        # 5 requests should all pass
        for _ in range(5):
            limiter.check(request)

    def test_blocks_at_limit(self):
        """Should raise HTTPException(429) when the limit is reached."""
        limiter = RateLimiter(requests_per_minute=3)
        request = _make_request(client_host="10.0.0.1")

        # 3 requests pass
        for _ in range(3):
            limiter.check(request)

        # 4th request should be blocked
        with pytest.raises(HTTPException) as exc_info:
            limiter.check(request)

        assert exc_info.value.status_code == 429
        assert "Rate limit exceeded" in exc_info.value.detail
        assert exc_info.value.headers["Retry-After"] == "60"

    def test_sliding_window_clears_old_entries(self):
        """Old timestamps outside the 60s window should be cleaned up."""
        limiter = RateLimiter(requests_per_minute=2)
        request = _make_request(client_host="10.0.0.1")

        # Manually inject old timestamps (> 60s ago)
        old_time = time.time() - 120.0  # 2 minutes ago
        client_id = limiter._get_client_id(request)
        limiter._windows[client_id] = [old_time, old_time + 1]

        # These old entries should be cleaned, so new request should pass
        limiter.check(request)

        # Only the new timestamp should remain
        assert len(limiter._windows[client_id]) == 1

    def test_per_client_isolation(self):
        """Each client should have independent rate limits."""
        limiter = RateLimiter(requests_per_minute=2)

        client_a = _make_request(client_host="10.0.0.1")
        client_b = _make_request(client_host="10.0.0.2")

        # Exhaust client A's limit
        limiter.check(client_a)
        limiter.check(client_a)
        with pytest.raises(HTTPException):
            limiter.check(client_a)

        # Client B should still pass
        limiter.check(client_b)
        limiter.check(client_b)

    def test_rate_limit_resets_after_window(self):
        """After the window passes, the client should be allowed again."""
        limiter = RateLimiter(requests_per_minute=1)
        request = _make_request(client_host="10.0.0.1")

        # Fill the limit
        limiter.check(request)
        with pytest.raises(HTTPException):
            limiter.check(request)

        # Move all timestamps to the past (simulate time passing)
        client_id = limiter._get_client_id(request)
        limiter._windows[client_id] = [time.time() - 120.0]

        # Now the request should pass again
        limiter.check(request)
