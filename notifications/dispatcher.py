import logging

from sqlalchemy import select

from storage.database import get_session
from storage.models import Subscription

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    """Dispatches article notifications to matching subscriptions."""

    async def dispatch(self, article_dict: dict):
        """Check all subscriptions and send matching notifications."""
        from api.websocket import ws_manager
        from notifications.webhook import WebhookDeliverer

        # 1. Always broadcast to WebSocket clients (they do their own filtering)
        await ws_manager.broadcast_article(article_dict)

        # 2. Find matching webhook subscriptions
        webhook_deliverer = WebhookDeliverer()
        try:
            subs = await self._find_matching_subscriptions(
                article_dict, channel="webhook"
            )
            for sub in subs:
                url = (sub.channel_config or {}).get("url")
                secret = (sub.channel_config or {}).get("secret")
                if url:
                    await webhook_deliverer.deliver(
                        subscription_id=sub.id,
                        article_id=article_dict.get("id", ""),
                        url=url,
                        payload={"event": "new_article", "article": article_dict},
                        secret=secret,
                    )
        finally:
            await webhook_deliverer.close()

    async def _find_matching_subscriptions(
        self, article: dict, channel: str
    ) -> list:
        async with get_session() as session:
            query = select(Subscription).where(
                Subscription.enabled == True,  # noqa: E712
                Subscription.channel == channel,
                Subscription.frequency == "realtime",
            )
            result = await session.execute(query)
            subs = result.scalars().all()

        return [s for s in subs if self._matches(s, article)]

    @staticmethod
    def _matches(sub: Subscription, article: dict) -> bool:
        if sub.source_ids and article.get("source_id") not in sub.source_ids:
            return False
        if sub.transport_modes:
            article_modes = article.get("transport_modes") or []
            if not set(sub.transport_modes) & set(article_modes):
                return False
        if sub.topics and article.get("primary_topic") not in sub.topics:
            return False
        if sub.regions:
            article_regions = article.get("regions") or []
            if not set(sub.regions) & set(article_regions):
                return False
        if sub.languages and article.get("language") not in sub.languages:
            return False
        return True
