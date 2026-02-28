"""Source candidate validator.

For each SourceCandidate, performs:
1. Connectivity check — can we reach the site?
2. RSS/feed probe — does it have a discoverable feed?
3. Trial article fetch — can we extract real articles?
4. Quality scoring — article completeness (title, body, date)
5. Relevance scoring — logistics keyword matching
6. Dedup check — is it an alias of an existing source?

Produces a 0-100 quality_score and 0-100 relevance_score.
Candidates above the auto_approve_threshold are promoted automatically.
"""

import asyncio
import logging
import re
from datetime import datetime
from urllib.parse import urlparse

import httpx
import yaml
from bs4 import BeautifulSoup
from sqlalchemy import select, update

from adapters.universal_adapter import UniversalAdapter
from config.settings import settings
from storage.database import get_session
from storage.models import Source, SourceCandidate

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "LogisticsNewsDiscovery/1.0 "
    "(+https://github.com/logistics-news; source validation bot)"
)


def _load_relevance_keywords() -> dict:
    with open(settings.discovery_seeds_path, "r") as f:
        data = yaml.safe_load(f)
    return data.get("relevance_keywords", {})


class SourceValidator:
    """Validates source candidates and assigns quality/relevance scores."""

    def __init__(self):
        self.relevance_kw = _load_relevance_keywords()
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(20.0, connect=10.0),
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
        )

    async def close(self):
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    async def validate_batch(self, limit: int = 20) -> dict:
        """Validate a batch of 'discovered' candidates. Returns summary."""
        async with get_session() as session:
            result = await session.execute(
                select(SourceCandidate)
                .where(SourceCandidate.status == "discovered")
                .order_by(SourceCandidate.created_at)
                .limit(limit)
            )
            candidates = list(result.scalars().all())
            candidate_ids = [c.id for c in candidates]

        if not candidates:
            return {"validated": 0, "auto_approved": 0}

        # Mark as validating
        async with get_session() as session:
            await session.execute(
                update(SourceCandidate)
                .where(SourceCandidate.id.in_(candidate_ids))
                .values(status="validating")
            )

        validated = 0
        auto_approved = 0

        for candidate in candidates:
            try:
                result = await self._validate_one(candidate)
                validated += 1
                if result.get("auto_approved"):
                    auto_approved += 1
            except Exception as e:
                logger.warning(
                    f"Validation failed for {candidate.url}: {e}"
                )
                async with get_session() as session:
                    await session.execute(
                        update(SourceCandidate)
                        .where(SourceCandidate.id == candidate.id)
                        .values(
                            status="validated",
                            fetch_success=False,
                            error_message=str(e)[:500],
                            validated_at=datetime.utcnow(),
                            quality_score=0,
                            relevance_score=0,
                        )
                    )
            await asyncio.sleep(2.0)  # politeness between candidates

        summary = {
            "validated": validated,
            "auto_approved": auto_approved,
        }
        logger.info(f"Validation batch complete: {summary}")
        return summary

    async def validate_single(self, candidate_id: str) -> dict:
        """Validate a single candidate by ID. Returns validation result."""
        async with get_session() as session:
            result = await session.execute(
                select(SourceCandidate).where(
                    SourceCandidate.id == candidate_id
                )
            )
            candidate = result.scalar_one_or_none()

        if not candidate:
            raise ValueError(f"Candidate {candidate_id} not found")

        async with get_session() as session:
            await session.execute(
                update(SourceCandidate)
                .where(SourceCandidate.id == candidate_id)
                .values(status="validating")
            )

        return await self._validate_one(candidate)

    # ------------------------------------------------------------------
    # Internal validation pipeline
    # ------------------------------------------------------------------

    async def _validate_one(self, candidate: SourceCandidate) -> dict:
        """Run the full validation pipeline on a single candidate."""
        url = candidate.url
        details: dict = {}

        # Step 1: Connectivity
        reachable, page_html, final_url = await self._check_connectivity(url)
        details["reachable"] = reachable
        details["final_url"] = final_url

        if not reachable:
            await self._save_result(
                candidate.id,
                quality_score=0,
                relevance_score=0,
                fetch_success=False,
                details=details,
                error="Site unreachable",
            )
            return {"candidate_id": candidate.id, "quality_score": 0, "auto_approved": False}

        # Step 2: Try to detect site name from page
        site_name = self._extract_site_name(page_html, url)
        details["detected_name"] = site_name

        # Step 3: RSS/feed probe
        feed_url = await self._probe_feed(url, page_html)
        details["feed_url"] = feed_url
        source_type = "rss" if feed_url else "universal"

        # Step 4: Trial article fetch via UniversalAdapter
        articles, fetch_error = await self._trial_fetch(url, site_name, candidate.language)
        details["articles_fetched"] = len(articles)
        details["fetch_error"] = fetch_error

        if not articles:
            await self._save_result(
                candidate.id,
                name=site_name,
                feed_url=feed_url,
                source_type=source_type,
                quality_score=10,
                relevance_score=0,
                fetch_success=False,
                details=details,
                error=fetch_error or "No articles extracted",
            )
            return {"candidate_id": candidate.id, "quality_score": 10, "auto_approved": False}

        # Step 5: Quality scoring
        quality_score = self._score_quality(articles)
        details["quality_breakdown"] = self._quality_breakdown(articles)

        # Step 6: Relevance scoring
        relevance_score = self._score_relevance(articles, candidate.language or "en")
        details["relevance_breakdown"] = {"score": relevance_score}

        # Step 7: Sample articles for preview
        samples = [
            {
                "title": a.get("title", "")[:200],
                "url": a.get("url", ""),
                "body_preview": (a.get("body_text") or "")[:300],
                "published_at": a.get("published_at"),
            }
            for a in articles[:5]
        ]

        # Step 8: Compute combined score and check auto-approve
        combined = int(quality_score * 0.4 + relevance_score * 0.6)
        threshold = settings.discovery_auto_approve_threshold
        auto_approved = combined >= threshold

        status = "approved" if auto_approved else "validated"
        await self._save_result(
            candidate.id,
            name=site_name,
            feed_url=feed_url,
            source_type=source_type,
            quality_score=quality_score,
            relevance_score=relevance_score,
            fetch_success=True,
            articles_fetched=len(articles),
            samples=samples,
            details=details,
            auto_approved=auto_approved,
            status=status,
        )

        # Auto-approve: promote to Source
        if auto_approved:
            await self._promote_to_source(candidate, site_name, feed_url, source_type)

        return {
            "candidate_id": candidate.id,
            "quality_score": quality_score,
            "relevance_score": relevance_score,
            "combined_score": combined,
            "auto_approved": auto_approved,
            "articles_fetched": len(articles),
        }

    # ------------------------------------------------------------------
    # Step helpers
    # ------------------------------------------------------------------

    async def _check_connectivity(
        self, url: str
    ) -> tuple[bool, str | None, str | None]:
        """Check if URL is reachable. Returns (reachable, html, final_url)."""
        try:
            resp = await self.client.get(url)
            resp.raise_for_status()
            return True, resp.text, str(resp.url)
        except Exception as e:
            logger.debug(f"Connectivity check failed for {url}: {e}")
            return False, None, None

    def _extract_site_name(self, html: str | None, url: str) -> str:
        """Try to extract the site name from the HTML <title> tag."""
        if not html:
            return urlparse(url).netloc
        try:
            soup = BeautifulSoup(html, "lxml")
            title_tag = soup.find("title")
            if title_tag and title_tag.string:
                # Clean common suffixes like " - Home", " | News"
                name = title_tag.string.strip()
                name = re.split(r"\s*[|\-–—]\s*", name)[0].strip()
                if len(name) > 3:
                    return name[:200]
        except Exception:
            pass
        return urlparse(url).netloc

    async def _probe_feed(self, url: str, html: str | None) -> str | None:
        """Look for RSS/Atom feed URL."""
        # Check HTML <link> tags
        if html:
            soup = BeautifulSoup(html, "lxml")
            for link_type in (
                "application/rss+xml",
                "application/atom+xml",
            ):
                link = soup.find(
                    "link", attrs={"rel": "alternate", "type": link_type}
                )
                if link and link.get("href"):
                    from urllib.parse import urljoin

                    feed_url = urljoin(url, link["href"])
                    if await self._is_valid_feed(feed_url):
                        return feed_url

        # Try common paths
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        for path in ["/feed", "/rss", "/atom.xml", "/feed.xml", "/rss.xml"]:
            candidate = base + path
            if await self._is_valid_feed(candidate):
                return candidate

        return None

    async def _is_valid_feed(self, feed_url: str) -> bool:
        """Quick check if a URL returns valid RSS/Atom content."""
        try:
            resp = await self.client.get(feed_url)
            resp.raise_for_status()
            text = resp.text[:2000]
            return "<rss" in text or "<feed" in text or "<rdf" in text.lower()
        except Exception:
            return False

    async def _trial_fetch(
        self, url: str, name: str, language: str | None
    ) -> tuple[list[dict], str | None]:
        """Try fetching articles using UniversalAdapter."""
        config = {
            "source_id": "__discovery_probe__",
            "name": name or "Probe",
            "url": url,
            "type": "universal",
            "language": language or "en",
            "max_articles": 5,
        }
        try:
            async with UniversalAdapter(config) as adapter:
                raw_articles = await adapter.fetch()
            articles = [
                {
                    "title": a.title,
                    "url": a.url,
                    "body_text": a.body_text,
                    "published_at": a.published_at.isoformat()
                    if a.published_at
                    else None,
                }
                for a in raw_articles
            ]
            return articles, None
        except Exception as e:
            return [], str(e)[:500]

    def _score_quality(self, articles: list[dict]) -> int:
        """Score article quality 0-100 based on completeness."""
        if not articles:
            return 0

        total = 0
        for a in articles:
            score = 0
            # Has title (+20)
            if a.get("title") and len(a["title"]) > 10:
                score += 20
            # Has body (+40)
            body = a.get("body_text") or ""
            if len(body) > 200:
                score += 40
            elif len(body) > 50:
                score += 20
            # Has date (+20)
            if a.get("published_at"):
                score += 20
            # Has reasonable URL (+20)
            if a.get("url") and len(a["url"]) > 20:
                score += 20
            total += score

        return min(100, total // len(articles))

    def _quality_breakdown(self, articles: list[dict]) -> dict:
        """Return breakdown of quality metrics."""
        has_title = sum(1 for a in articles if a.get("title") and len(a["title"]) > 10)
        has_body = sum(1 for a in articles if (a.get("body_text") or "") and len(a.get("body_text", "")) > 200)
        has_date = sum(1 for a in articles if a.get("published_at"))
        total = len(articles)
        return {
            "total_articles": total,
            "with_title": has_title,
            "with_body": has_body,
            "with_date": has_date,
        }

    def _score_relevance(self, articles: list[dict], language: str) -> int:
        """Score logistics relevance 0-100 based on keyword matching."""
        lang_key = "zh" if language.startswith("zh") else "en"
        kw_config = self.relevance_kw.get(lang_key, {})

        high = [k.lower() for k in kw_config.get("high_weight", [])]
        medium = [k.lower() for k in kw_config.get("medium_weight", [])]
        low = [k.lower() for k in kw_config.get("low_weight", [])]

        total_score = 0
        for a in articles:
            text = (
                (a.get("title") or "") + " " + (a.get("body_text") or "")
            ).lower()

            article_score = 0
            for kw in high:
                if kw in text:
                    article_score += 10
            for kw in medium:
                if kw in text:
                    article_score += 5
            for kw in low:
                if kw in text:
                    article_score += 2

            total_score += min(article_score, 100)

        avg = total_score / len(articles) if articles else 0
        return min(100, int(avg))

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    async def _save_result(
        self,
        candidate_id: str,
        *,
        name: str | None = None,
        feed_url: str | None = None,
        source_type: str | None = None,
        quality_score: int = 0,
        relevance_score: int = 0,
        fetch_success: bool = False,
        articles_fetched: int = 0,
        samples: list | None = None,
        details: dict | None = None,
        error: str | None = None,
        auto_approved: bool = False,
        status: str = "validated",
    ):
        values: dict = {
            "status": status,
            "quality_score": quality_score,
            "relevance_score": relevance_score,
            "fetch_success": fetch_success,
            "articles_fetched": articles_fetched,
            "validation_details": details or {},
            "sample_articles": samples or [],
            "error_message": error,
            "auto_approved": auto_approved,
            "validated_at": datetime.utcnow(),
        }
        if name:
            values["name"] = name
        if feed_url:
            values["feed_url"] = feed_url
        if source_type:
            values["source_type"] = source_type

        async with get_session() as session:
            await session.execute(
                update(SourceCandidate)
                .where(SourceCandidate.id == candidate_id)
                .values(**values)
            )

    async def _promote_to_source(
        self,
        candidate: SourceCandidate,
        name: str | None,
        feed_url: str | None,
        source_type: str,
    ):
        """Promote a validated candidate to the sources table."""
        # Build a unique source_id
        domain = urlparse(candidate.url).netloc.replace("www.", "")
        source_id = re.sub(r"[^a-z0-9]", "_", domain.lower()) + "_auto"

        async with get_session() as session:
            # Check not already a source
            existing = await session.execute(
                select(Source.source_id).where(Source.source_id == source_id)
            )
            if existing.scalar_one_or_none():
                logger.info(f"Source {source_id} already exists, skipping promote")
                return

            url = feed_url or candidate.url
            source = Source(
                source_id=source_id,
                name=name or domain,
                type=source_type,
                url=url,
                language=candidate.language,
                categories=candidate.categories or [],
                fetch_interval_minutes=60,
                enabled=True,
                priority=3,
                notes=f"Auto-discovered via {candidate.discovered_via}",
            )
            session.add(source)

        logger.info(f"Auto-promoted candidate → source: {source_id} ({name})")
