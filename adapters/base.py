import logging
import ssl
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

USER_AGENT = (
    "LogisticsNewsCollector/1.0 "
    "(+https://github.com/logistics-news; news aggregation bot)"
)


def _make_weak_ssl_context() -> ssl.SSLContext:
    """Create a permissive SSL context for sites with weak/legacy ciphers."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


@dataclass
class RawArticle:
    """Raw article data from any adapter before processing."""

    source_id: str
    source_name: str
    url: str
    title: str
    body_text: str | None = None
    body_markdown: str | None = None
    body_html: str | None = None
    published_at: datetime | None = None
    fetched_at: datetime = field(default_factory=datetime.utcnow)
    language: str | None = None
    raw_metadata: dict = field(default_factory=dict)


class BaseAdapter(ABC):
    """Abstract base class for all source adapters."""

    def __init__(self, source_config: dict):
        self.config = source_config
        self.source_id = source_config["source_id"]
        self.source_name = source_config["name"]

        scraper_cfg: dict = source_config.get("scraper_config") or {}
        ssl_weak = scraper_cfg.get("ssl_weak", False)

        verify: ssl.SSLContext | bool = _make_weak_ssl_context() if ssl_weak else True

        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            verify=verify,
        )

    @abstractmethod
    async def fetch(self) -> list[RawArticle]:
        """Fetch new articles from the source. Must be implemented by subclasses."""
        ...

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
