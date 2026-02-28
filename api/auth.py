import hashlib
import logging
import secrets

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader
from sqlalchemy import select

from storage.database import get_session

logger = logging.getLogger(__name__)

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def hash_api_key(key: str) -> str:
    """Hash an API key using SHA-256."""
    return hashlib.sha256(key.encode()).hexdigest()


def generate_api_key() -> str:
    """Generate a random API key."""
    return f"lnc_{secrets.token_urlsafe(32)}"


async def get_current_api_key(api_key: str | None = Security(API_KEY_HEADER)):
    """Dependency that validates the API key.

    If no API key is configured in the system (no keys in DB),
    allows open access (for development).
    If keys exist, requires a valid key.
    """
    from storage.models import APIKey

    async with get_session() as session:
        # Check if any API keys exist
        result = await session.execute(select(APIKey.id).limit(1))
        has_keys = result.scalar_one_or_none() is not None

    if not has_keys:
        return None  # Open access mode - no keys configured

    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")

    key_hash = hash_api_key(api_key)
    async with get_session() as session:
        result = await session.execute(
            select(APIKey).where(
                APIKey.key_hash == key_hash,
                APIKey.enabled == True,
            )
        )
        db_key = result.scalar_one_or_none()

    if not db_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return db_key
