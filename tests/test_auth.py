"""
Tests for api/auth.py -- API key hashing, generation, and authentication.

All database access is mocked.
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from api.auth import generate_api_key, get_current_api_key, hash_api_key


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_get_session(mock_session):
    """Create a patched get_session that yields mock_session."""

    @asynccontextmanager
    async def _fake():
        yield mock_session

    return _fake


# ---------------------------------------------------------------------------
# hash_api_key
# ---------------------------------------------------------------------------


class TestHashApiKey:
    """hash_api_key should produce consistent SHA-256 hex digests."""

    def test_consistent_hashing(self):
        """Same input should always produce the same hash."""
        key = "lnc_test_key_123"
        assert hash_api_key(key) == hash_api_key(key)

    def test_different_inputs_different_hashes(self):
        """Different inputs should produce different hashes."""
        hash1 = hash_api_key("key_one")
        hash2 = hash_api_key("key_two")
        assert hash1 != hash2

    def test_returns_hex_string(self):
        """Hash output should be a valid 64-char hex string (SHA-256)."""
        result = hash_api_key("test_key")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_empty_string(self):
        """Hashing an empty string should still produce a valid hash."""
        result = hash_api_key("")
        assert len(result) == 64


# ---------------------------------------------------------------------------
# generate_api_key
# ---------------------------------------------------------------------------


class TestGenerateApiKey:
    """generate_api_key should produce secure, properly prefixed keys."""

    def test_starts_with_prefix(self):
        """Generated keys should start with 'lnc_'."""
        key = generate_api_key()
        assert key.startswith("lnc_")

    def test_sufficient_length(self):
        """Generated keys should be long enough to be secure."""
        key = generate_api_key()
        # "lnc_" prefix (4 chars) + 32 bytes urlsafe base64 (~43 chars)
        assert len(key) > 40

    def test_unique_each_time(self):
        """Each call should produce a different key."""
        keys = {generate_api_key() for _ in range(10)}
        assert len(keys) == 10


# ---------------------------------------------------------------------------
# get_current_api_key
# ---------------------------------------------------------------------------


class TestGetCurrentApiKeyOpenAccess:
    """When no API keys exist in the DB, open access mode should be enabled."""

    async def test_open_access_when_no_keys(self):
        """Should return None (open access) when no keys are configured."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # No keys in DB
        mock_session.execute = AsyncMock(return_value=mock_result)

        fake_get_session = _make_fake_get_session(mock_session)

        with patch("api.auth.get_session", new=fake_get_session):
            result = await get_current_api_key(api_key=None)

        assert result is None


class TestGetCurrentApiKeyRequired:
    """When API keys exist in the DB, authentication should be enforced."""

    async def test_requires_key_when_keys_exist(self):
        """Should raise 401 when keys exist but no key is provided."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = 1  # Keys exist
        mock_session.execute = AsyncMock(return_value=mock_result)

        fake_get_session = _make_fake_get_session(mock_session)

        with patch("api.auth.get_session", new=fake_get_session):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_api_key(api_key=None)

        assert exc_info.value.status_code == 401
        assert "API key required" in exc_info.value.detail

    async def test_rejects_invalid_key(self):
        """Should raise 401 when the provided key is not found in the DB."""
        mock_session = AsyncMock()

        # First call: check if keys exist -> yes
        check_result = MagicMock()
        check_result.scalar_one_or_none.return_value = 1

        # Second call: look up key_hash -> not found
        lookup_result = MagicMock()
        lookup_result.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(
            side_effect=[check_result, lookup_result]
        )

        fake_get_session = _make_fake_get_session(mock_session)

        with patch("api.auth.get_session", new=fake_get_session):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_api_key(api_key="lnc_invalid_key")

        assert exc_info.value.status_code == 401
        assert "Invalid API key" in exc_info.value.detail

    async def test_accepts_valid_key(self):
        """Should return the DB key object when a valid, enabled key is provided."""
        mock_db_key = MagicMock()
        mock_db_key.id = "key-uuid-123"
        mock_db_key.name = "test-key"
        mock_db_key.enabled = True

        mock_session = AsyncMock()

        # First call: check if keys exist -> yes
        check_result = MagicMock()
        check_result.scalar_one_or_none.return_value = 1

        # Second call: look up key_hash -> found
        lookup_result = MagicMock()
        lookup_result.scalar_one_or_none.return_value = mock_db_key

        mock_session.execute = AsyncMock(
            side_effect=[check_result, lookup_result]
        )

        fake_get_session = _make_fake_get_session(mock_session)

        with patch("api.auth.get_session", new=fake_get_session):
            result = await get_current_api_key(api_key="lnc_valid_key")

        assert result is mock_db_key

    async def test_rejects_disabled_key(self):
        """Should raise 401 for a key that exists but is disabled.

        The SQL query filters by enabled=True, so a disabled key won't be
        returned by the query -- scalar_one_or_none returns None.
        """
        mock_session = AsyncMock()

        # First call: check if keys exist -> yes
        check_result = MagicMock()
        check_result.scalar_one_or_none.return_value = 1

        # Second call: look up key_hash with enabled=True -> not found
        lookup_result = MagicMock()
        lookup_result.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(
            side_effect=[check_result, lookup_result]
        )

        fake_get_session = _make_fake_get_session(mock_session)

        with patch("api.auth.get_session", new=fake_get_session):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_api_key(api_key="lnc_disabled_key")

        assert exc_info.value.status_code == 401
        assert "Invalid API key" in exc_info.value.detail
