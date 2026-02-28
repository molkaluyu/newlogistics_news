"""Source discovery engine.

Discovers new logistics news sources via:
1. Web search — DuckDuckGo (free, default) or Google CSE (optional)
2. Seed URL expansion: crawl known sites for outbound links to other news sites
3. RSS probe: test discovered URLs for RSS/Atom feeds

The engine produces SourceCandidate rows that are later validated.
"""

import asyncio
import logging
import re
from urllib.parse import urljoin, urlparse

import httpx
import yaml
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from sqlalchemy import select

from config.settings import settings
from storage.database import get_session
from storage.models import Source, SourceCandidate

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "LogisticsNewsDiscovery/1.0 "
    "(+https://github.com/logistics-news; source discovery bot)"
)

# Domains we should never add as sources (social media, search engines, etc.)
_BLOCKED_DOMAINS = {
    "google.com", "bing.com", "yahoo.com", "baidu.com",
    "facebook.com", "twitter.com", "x.com", "instagram.com",
    "linkedin.com", "youtube.com", "tiktok.com", "reddit.com",
    "wikipedia.org", "amazon.com", "ebay.com", "alibaba.com",
    "github.com", "stackoverflow.com",
}


def _load_seeds() -> dict:
    """Load discovery seeds from YAML."""
    with open(settings.discovery_seeds_path, "r") as f:
        return yaml.safe_load(f)


def _extract_domain(url: str) -> str:
    """Return the registrable domain from a URL (e.g. 'www.foo.com' → 'foo.com')."""
    host = urlparse(url).netloc.lower()
    parts = host.split(".")
    if len(parts) > 2 and parts[0] == "www":
        parts = parts[1:]
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def _is_blocked(url: str) -> bool:
    domain = _extract_domain(url)
    return any(domain.endswith(b) for b in _BLOCKED_DOMAINS)


class DiscoveryEngine:
    """Discovers new logistics news source candidates."""

    def __init__(self):
        self.seeds = _load_seeds()
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(20.0, connect=10.0),
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
        )
        self._known_domains: set[str] = set()
        self._candidate_urls: set[str] = set()

    async def close(self):
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def run(self, max_candidates: int | None = None) -> list[dict]:
        """Run the full discovery pipeline. Returns list of new candidate dicts."""
        max_candidates = max_candidates or settings.discovery_max_candidates_per_run

        # Load known sources/candidates so we skip duplicates
        await self._load_known_domains()

        candidates: list[dict] = []

        # Phase 1: Web search
        # Use Google CSE if configured, otherwise DuckDuckGo (free, no API key)
        if settings.discovery_search_api and settings.discovery_search_engine_id:
            web_results = await self._search_via_google_cse()
            candidates.extend(web_results)
        else:
            web_results = await self._search_via_duckduckgo()
            candidates.extend(web_results)

        # Phase 2: Seed URL expansion (crawl outbound links)
        seed_results = await self._expand_seed_urls()
        candidates.extend(seed_results)

        # Deduplicate and cap
        seen: set[str] = set()
        unique: list[dict] = []
        for c in candidates:
            domain = _extract_domain(c["url"])
            if domain not in seen and domain not in self._known_domains:
                seen.add(domain)
                unique.append(c)
            if len(unique) >= max_candidates:
                break

        # Persist candidates to DB
        saved = await self._save_candidates(unique)
        logger.info(f"Discovery complete: {len(saved)} new candidates saved")
        return saved

    # ------------------------------------------------------------------
    # Phase 1a: DuckDuckGo search (free, no API key required)
    # ------------------------------------------------------------------

    async def _search_via_duckduckgo(self) -> list[dict]:
        """Use DuckDuckGo to search for new sources. Free, no API key needed."""
        candidates: list[dict] = []
        queries = self.seeds.get("search_queries", {})

        for lang, query_list in queries.items():
            region = "cn-zh" if lang == "zh" else "us-en"
            for query in query_list[:5]:  # limit queries per run
                try:
                    results = await asyncio.to_thread(
                        self._ddg_search, query, region
                    )
                    for r in results:
                        if not _is_blocked(r["url"]):
                            r["discovered_via"] = "web_search"
                            r["discovery_query"] = query
                            r["language"] = lang
                            candidates.append(r)
                except Exception as e:
                    logger.warning(
                        f"Discovery: DuckDuckGo search failed for '{query}': {e}"
                    )
                await asyncio.sleep(2.0)  # politeness between queries

        logger.info(f"Discovery: DuckDuckGo found {len(candidates)} raw results")
        return candidates

    @staticmethod
    def _ddg_search(query: str, region: str) -> list[dict]:
        """Synchronous DuckDuckGo search (runs in thread)."""
        results: list[dict] = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, region=region, max_results=10):
                link = r.get("href", "")
                if not link:
                    continue
                parsed = urlparse(link)
                site_url = f"{parsed.scheme}://{parsed.netloc}"
                results.append({
                    "url": site_url,
                    "name": r.get("title", "")[:200],
                })
        return results

    # ------------------------------------------------------------------
    # Phase 1b: Google CSE (optional, requires API key)
    # ------------------------------------------------------------------

    async def _search_via_google_cse(self) -> list[dict]:
        """Use Google Custom Search API (requires DISCOVERY_SEARCH_API + ENGINE_ID)."""
        api_key = settings.discovery_search_api
        cx = settings.discovery_search_engine_id

        candidates: list[dict] = []
        queries = self.seeds.get("search_queries", {})

        for lang, query_list in queries.items():
            for query in query_list[:5]:
                try:
                    params = {
                        "key": api_key,
                        "cx": cx,
                        "q": query,
                        "num": 10,
                        "lr": f"lang_{lang}",
                    }
                    resp = await self.client.get(
                        "https://www.googleapis.com/customsearch/v1",
                        params=params,
                    )
                    resp.raise_for_status()
                    data = resp.json()

                    for item in data.get("items", []):
                        link = item.get("link", "")
                        parsed = urlparse(link)
                        site_url = f"{parsed.scheme}://{parsed.netloc}"
                        if not _is_blocked(site_url):
                            candidates.append({
                                "url": site_url,
                                "name": item.get("title", "")[:200],
                                "discovered_via": "web_search",
                                "discovery_query": query,
                                "language": lang,
                            })
                except Exception as e:
                    logger.warning(
                        f"Discovery: Google CSE failed for '{query}': {e}"
                    )
                await asyncio.sleep(1.0)

        logger.info(f"Discovery: Google CSE found {len(candidates)} raw results")
        return candidates

    # ------------------------------------------------------------------
    # Phase 2: Seed URL expansion
    # ------------------------------------------------------------------

    async def _expand_seed_urls(self) -> list[dict]:
        """Crawl seed URLs and extract outbound links to other news sites."""
        seed_urls = self.seeds.get("seed_urls", [])
        candidates: list[dict] = []

        tasks = [self._crawl_for_outbound(s) for s in seed_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Discovery: seed crawl failed: {result}")
                continue
            candidates.extend(result)

        return candidates

    async def _crawl_for_outbound(self, seed: dict) -> list[dict]:
        """Fetch a seed URL page and extract external links that look like news sites."""
        url = seed["url"]
        try:
            resp = await self.client.get(url)
            resp.raise_for_status()
        except Exception as e:
            logger.debug(f"Discovery: failed to fetch seed {url}: {e}")
            return []

        html = resp.text
        seed_domain = _extract_domain(url)
        soup = BeautifulSoup(html, "lxml")

        seen: set[str] = set()
        candidates: list[dict] = []

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            absolute = urljoin(url, href).split("#")[0].split("?")[0]
            parsed = urlparse(absolute)

            if not parsed.scheme.startswith("http"):
                continue

            domain = _extract_domain(absolute)
            if domain == seed_domain or domain in seen:
                continue
            if _is_blocked(absolute):
                continue

            seen.add(domain)
            site_url = f"{parsed.scheme}://{parsed.netloc}"
            link_text = anchor.get_text(strip=True)[:200]

            candidates.append({
                "url": site_url,
                "name": link_text or domain,
                "discovered_via": "seed_expansion",
                "discovery_query": f"outbound from {url}",
                "language": seed.get("language"),
                "categories": seed.get("categories", []),
            })

        return candidates

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    async def _load_known_domains(self):
        """Load domains of existing sources and candidates to avoid duplicates."""
        async with get_session() as session:
            # Existing approved sources
            result = await session.execute(select(Source.url))
            for row in result.scalars():
                self._known_domains.add(_extract_domain(row))

            # Existing candidates (any status)
            result = await session.execute(select(SourceCandidate.url))
            for row in result.scalars():
                self._known_domains.add(_extract_domain(row))

    async def _save_candidates(self, candidates: list[dict]) -> list[dict]:
        """Save new candidates to the database. Returns saved candidate dicts."""
        saved: list[dict] = []

        async with get_session() as session:
            for c in candidates:
                # Double-check uniqueness
                exists = await session.execute(
                    select(SourceCandidate.id).where(
                        SourceCandidate.url == c["url"]
                    )
                )
                if exists.scalar_one_or_none():
                    continue

                candidate = SourceCandidate(
                    url=c["url"],
                    name=c.get("name"),
                    language=c.get("language"),
                    categories=c.get("categories", []),
                    discovered_via=c.get("discovered_via"),
                    discovery_query=c.get("discovery_query"),
                    status="discovered",
                )
                session.add(candidate)
                await session.flush()
                saved.append({
                    "id": candidate.id,
                    "url": candidate.url,
                    "name": candidate.name,
                    "language": candidate.language,
                    "discovered_via": candidate.discovered_via,
                })

        return saved
