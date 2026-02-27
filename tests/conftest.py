"""
Shared pytest fixtures for the logistics news collector test suite.

Test dependencies: pytest, pytest-asyncio, httpx
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from adapters.base import RawArticle
from storage.models import Article, FetchLog, Source


# ---------------------------------------------------------------------------
# RawArticle fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_raw_article() -> RawArticle:
    """A single fully-populated RawArticle dataclass instance."""
    return RawArticle(
        source_id="loadstar_rss",
        source_name="The Loadstar",
        url="https://theloadstar.com/article/supply-chain-crisis-deepens",
        title="Supply chain crisis deepens - The Loadstar",
        body_text="Global supply chains continue to face unprecedented challenges...",
        body_markdown="# Supply chain crisis deepens\n\nGlobal supply chains continue...",
        body_html="<h1>Supply chain crisis deepens</h1><p>Global supply chains continue...</p>",
        published_at=datetime(2025, 6, 15, 10, 30, 0, tzinfo=timezone.utc),
        fetched_at=datetime(2025, 6, 15, 11, 0, 0, tzinfo=timezone.utc),
        language="en",
        raw_metadata={
            "rss_summary": "Global supply chains continue...",
            "rss_tags": ["ocean", "logistics"],
            "rss_author": "John Doe",
        },
    )


@pytest.fixture
def sample_raw_articles() -> list[RawArticle]:
    """Multiple RawArticle instances for batch-testing."""
    return [
        RawArticle(
            source_id="loadstar_rss",
            source_name="The Loadstar",
            url="https://theloadstar.com/article/port-congestion",
            title="Port congestion worsens",
            body_text="Major ports worldwide are experiencing severe congestion...",
            published_at=datetime(2025, 6, 15, 8, 0, 0, tzinfo=timezone.utc),
            language="en",
        ),
        RawArticle(
            source_id="freightwaves_rss",
            source_name="FreightWaves",
            url="https://www.freightwaves.com/article/air-cargo-rates",
            title="Air cargo rates surge amid holiday rush | FreightWaves",
            body_text="Air cargo spot rates have jumped 25% in the past week...",
            published_at=datetime(2025, 6, 14, 14, 0, 0, tzinfo=timezone.utc),
            language="en",
        ),
        RawArticle(
            source_id="splash247_rss",
            source_name="Splash247",
            url="https://splash247.com/article/tanker-market-outlook",
            title="Tanker market outlook remains bullish",
            body_text="The tanker market continues to benefit from shifting trade patterns...",
            published_at=datetime(2025, 6, 13, 9, 0, 0, tzinfo=timezone.utc),
            language="en",
        ),
    ]


# ---------------------------------------------------------------------------
# ORM model fixtures (plain Python objects, NOT persisted to any DB)
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_source() -> Source:
    """A Source ORM model instance (not persisted)."""
    source = Source.__new__(Source)
    source.source_id = "loadstar_rss"
    source.name = "The Loadstar"
    source.type = "rss"
    source.url = "https://theloadstar.com/feed/"
    source.language = "en"
    source.categories = ["ocean", "air", "logistics"]
    source.fetch_interval_minutes = 30
    source.parser_config = {}
    source.scraper_config = {}
    source.enabled = True
    source.priority = 1
    source.last_fetched_at = datetime(2025, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
    source.health_status = "healthy"
    source.notes = "Free, frequently updated"
    source.created_at = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    return source


@pytest.fixture
def sample_article() -> Article:
    """An Article ORM model instance (not persisted)."""
    article = Article.__new__(Article)
    article.id = "550e8400-e29b-41d4-a716-446655440000"
    article.source_id = "loadstar_rss"
    article.source_name = "The Loadstar"
    article.url = "https://theloadstar.com/article/supply-chain-crisis"
    article.title = "Supply chain crisis deepens"
    article.body_text = "Global supply chains continue to face challenges..."
    article.body_markdown = "# Supply chain crisis\n\nGlobal supply chains..."
    article.language = "en"
    article.published_at = datetime(2025, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
    article.fetched_at = datetime(2025, 6, 15, 11, 0, 0, tzinfo=timezone.utc)
    article.summary_en = "Supply chains face major challenges globally."
    article.summary_zh = None
    article.transport_modes = ["ocean"]
    article.primary_topic = "supply_chain_disruption"
    article.secondary_topics = ["port_congestion"]
    article.content_type = "news"
    article.regions = ["global"]
    article.entities = {"companies": ["Maersk"], "ports": ["Shanghai"]}
    article.sentiment = "negative"
    article.market_impact = "high"
    article.urgency = "high"
    article.key_metrics = [{"type": "rate_change", "value": "+15%"}]
    article.embedding = None
    article.raw_metadata = {"rss_author": "John Doe"}
    article.processing_status = "completed"
    article.llm_processed = True
    article.created_at = datetime(2025, 6, 15, 11, 0, 0, tzinfo=timezone.utc)
    article.updated_at = datetime(2025, 6, 15, 11, 5, 0, tzinfo=timezone.utc)
    return article


@pytest.fixture
def sample_fetch_log() -> FetchLog:
    """A FetchLog ORM model instance (not persisted)."""
    log = FetchLog.__new__(FetchLog)
    log.id = 1
    log.source_id = "loadstar_rss"
    log.started_at = datetime(2025, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
    log.completed_at = datetime(2025, 6, 15, 10, 0, 5, tzinfo=timezone.utc)
    log.status = "success"
    log.articles_found = 10
    log.articles_new = 7
    log.articles_dedup = 3
    log.error_message = None
    log.duration_ms = 5000
    return log


# ---------------------------------------------------------------------------
# Mock database session
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_session():
    """
    An AsyncMock that mimics an async SQLAlchemy session.

    Usage in tests:
        mock_session.execute.return_value = mock_result
    """
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def mock_get_session(mock_session):
    """
    Patch storage.database.get_session so it yields mock_session.

    Returns a context-manager-compatible mock that can be used as:
        async with get_session() as session:
            ...
    """
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _fake_get_session():
        yield mock_session

    patcher = patch("storage.database.get_session", new=_fake_get_session)
    patcher.start()
    yield mock_session
    patcher.stop()


# ---------------------------------------------------------------------------
# FastAPI test client (uses httpx AsyncClient with ASGI transport)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_app_get_session(mock_session):
    """
    Patch get_session specifically for the api.routes module so that
    the route handlers receive our mock_session.
    """
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _fake_get_session():
        yield mock_session

    patcher = patch("api.routes.get_session", new=_fake_get_session)
    patcher.start()
    yield mock_session
    patcher.stop()


@pytest.fixture
async def async_client(mock_app_get_session):
    """
    An httpx.AsyncClient wired to the FastAPI app (no lifespan to avoid
    real DB init / scheduler startup).

    The database is already mocked via mock_app_get_session.
    """
    from api.routes import router
    from fastapi import FastAPI

    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/v1")

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# Mock RSS feed XML data
# ---------------------------------------------------------------------------

MOCK_RSS_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>The Loadstar</title>
    <link>https://theloadstar.com</link>
    <description>Logistics news</description>
    <item>
      <title>Container shipping rates plummet</title>
      <link>https://theloadstar.com/container-shipping-rates-plummet/</link>
      <pubDate>Mon, 16 Jun 2025 08:00:00 +0000</pubDate>
      <description>&lt;p&gt;Rates on major east-west routes have dropped significantly.&lt;/p&gt;</description>
      <author>Jane Smith</author>
      <category>ocean</category>
    </item>
    <item>
      <title>Air cargo demand hits record high</title>
      <link>https://theloadstar.com/air-cargo-demand-record/</link>
      <pubDate>Sun, 15 Jun 2025 12:00:00 +0000</pubDate>
      <description>&lt;p&gt;E-commerce volumes are driving unprecedented air cargo demand.&lt;/p&gt;</description>
      <author>Bob Johnson</author>
      <category>air</category>
    </item>
  </channel>
</rss>
"""


@pytest.fixture
def mock_rss_xml() -> str:
    """Return sample RSS XML for testing feed parsing."""
    return MOCK_RSS_XML
