import asyncio
import hashlib
import hmac
import json
import logging

import httpx

from storage.database import get_session
from storage.models import WebhookDeliveryLog

logger = logging.getLogger(__name__)


class WebhookDeliverer:
    """Delivers article notifications to webhook URLs with HMAC signing."""

    MAX_RETRIES = 3
    RETRY_DELAYS = [2, 4, 8]  # seconds

    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    @staticmethod
    def sign_payload(payload: bytes, secret: str) -> str:
        return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    async def deliver(
        self,
        subscription_id: str,
        article_id: str,
        url: str,
        payload: dict,
        secret: str | None = None,
    ) -> bool:
        """Deliver webhook with retries and HMAC signing."""
        body = json.dumps(payload, default=str).encode()
        headers = {"Content-Type": "application/json"}
        if secret:
            sig = self.sign_payload(body, secret)
            headers["X-Webhook-Signature"] = f"sha256={sig}"

        client = await self._get_client()

        for attempt in range(1, self.MAX_RETRIES + 1):
            status_code = None
            error_msg = None
            success = False
            try:
                resp = await client.post(url, content=body, headers=headers)
                status_code = resp.status_code
                success = 200 <= status_code < 300
            except Exception as e:
                error_msg = str(e)[:500]

            await self._log_delivery(
                subscription_id,
                article_id,
                url,
                status_code,
                success,
                attempt,
                error_msg,
            )

            if success:
                return True

            if attempt < self.MAX_RETRIES:
                await asyncio.sleep(self.RETRY_DELAYS[attempt - 1])

        return False

    async def _log_delivery(
        self, sub_id, article_id, url, status, success, attempt, error
    ):
        try:
            async with get_session() as session:
                log = WebhookDeliveryLog(
                    subscription_id=sub_id,
                    article_id=article_id,
                    url=url,
                    status_code=status,
                    success=success,
                    attempt=attempt,
                    error_message=error,
                )
                session.add(log)
        except Exception as e:
            logger.error(f"Failed to log webhook delivery: {e}")

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
