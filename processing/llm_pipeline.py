import asyncio
import json
import logging
import time

import httpx
from sqlalchemy import select, update

from config.llm_settings import llm_settings
from processing.prompts import ARTICLE_ANALYSIS_SYSTEM_PROMPT, ARTICLE_ANALYSIS_USER_PROMPT
from storage.database import get_session
from storage.models import Article

logger = logging.getLogger(__name__)

# Fields extracted by the LLM that map directly to Article columns
LLM_FIELDS = [
    "summary_en",
    "summary_zh",
    "transport_modes",
    "primary_topic",
    "secondary_topics",
    "content_type",
    "regions",
    "entities",
    "sentiment",
    "market_impact",
    "urgency",
    "key_metrics",
]


class ArticleProcessor:
    """Process articles through an OpenAI-compatible LLM to extract structured metadata."""

    def __init__(self):
        self._client: httpx.AsyncClient | None = None
        # Simple rate limiter: track timestamps of recent requests
        self._request_timestamps: list[float] = []

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazy-init a shared httpx async client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=llm_settings.llm_base_url,
                headers={
                    "Authorization": f"Bearer {llm_settings.llm_api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(60.0, connect=10.0),
            )
        return self._client

    async def close(self):
        """Close the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    async def _wait_for_rate_limit(self):
        """Simple sliding-window rate limiter based on LLM_RATE_LIMIT_RPM."""
        rpm = llm_settings.llm_rate_limit_rpm
        if rpm <= 0:
            return

        now = time.monotonic()
        window = 60.0  # one minute

        # Purge timestamps older than the window
        self._request_timestamps = [
            ts for ts in self._request_timestamps if now - ts < window
        ]

        if len(self._request_timestamps) >= rpm:
            oldest = self._request_timestamps[0]
            sleep_for = window - (now - oldest) + 0.1
            if sleep_for > 0:
                logger.debug(f"Rate limit: sleeping {sleep_for:.1f}s")
                await asyncio.sleep(sleep_for)

        self._request_timestamps.append(time.monotonic())

    # ------------------------------------------------------------------
    # LLM calls
    # ------------------------------------------------------------------

    async def _call_chat(self, system_prompt: str, user_prompt: str) -> str:
        """Send a chat completion request and return the assistant message content."""
        await self._wait_for_rate_limit()
        client = await self._get_client()

        payload = {
            "model": llm_settings.llm_model,
            "temperature": llm_settings.llm_temperature,
            "max_tokens": llm_settings.llm_max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        response = await client.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    async def generate_embedding(self, text: str) -> list[float]:
        """Generate an embedding vector for the given text.

        Uses the configured embedding model and dimensions.
        Returns a list of floats (length = EMBEDDING_DIMENSIONS).
        """
        await self._wait_for_rate_limit()
        client = await self._get_client()

        payload = {
            "model": llm_settings.embedding_model,
            "input": text,
            "dimensions": llm_settings.embedding_dimensions,
        }

        response = await client.post("/embeddings", json=payload)
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["embedding"]

    # ------------------------------------------------------------------
    # JSON parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_llm_json(raw: str) -> dict:
        """Parse JSON from LLM output, stripping markdown fences if present."""
        text = raw.strip()

        # Strip ```json ... ``` or ``` ... ```
        if text.startswith("```"):
            # Remove opening fence line
            first_newline = text.index("\n")
            text = text[first_newline + 1 :]
            # Remove closing fence
            if text.endswith("```"):
                text = text[: -len("```")]
            text = text.strip()

        return json.loads(text)

    @staticmethod
    def _validate_extracted(data: dict) -> dict:
        """Sanitize and coerce the extracted fields to expected types."""
        validated: dict = {}

        # String fields with allowed values
        string_enums = {
            "sentiment": {"positive", "negative", "neutral", "mixed"},
            "market_impact": {"high", "medium", "low", "none"},
            "urgency": {"breaking", "high", "medium", "low"},
            "content_type": {"news", "analysis", "opinion", "press_release", "market_data"},
        }
        for field, allowed in string_enums.items():
            value = data.get(field)
            if isinstance(value, str) and value.lower() in allowed:
                validated[field] = value.lower()

        # primary_topic — free-form string from a known set but we don't reject unknowns
        if isinstance(data.get("primary_topic"), str) and data["primary_topic"]:
            validated["primary_topic"] = data["primary_topic"]

        # Plain text fields
        for field in ("summary_en", "summary_zh"):
            if isinstance(data.get(field), str) and data[field]:
                validated[field] = data[field]

        # Array-of-string fields
        for field in ("transport_modes", "secondary_topics", "regions"):
            value = data.get(field)
            if isinstance(value, list):
                validated[field] = [str(v) for v in value if v]

        # JSONB object — entities
        entities = data.get("entities")
        if isinstance(entities, dict):
            validated["entities"] = {
                "companies": [str(v) for v in entities.get("companies", []) if v],
                "ports": [str(v) for v in entities.get("ports", []) if v],
                "people": [str(v) for v in entities.get("people", []) if v],
                "organizations": [str(v) for v in entities.get("organizations", []) if v],
            }

        # JSONB array — key_metrics
        metrics = data.get("key_metrics")
        if isinstance(metrics, list):
            cleaned: list[dict] = []
            for m in metrics:
                if isinstance(m, dict) and "metric" in m and "value" in m:
                    cleaned.append({
                        "metric": str(m.get("metric", "")),
                        "value": str(m.get("value", "")),
                        "unit": str(m.get("unit", "")),
                        "context": str(m.get("context", "")),
                    })
            validated["key_metrics"] = cleaned

        return validated

    # ------------------------------------------------------------------
    # Core processing
    # ------------------------------------------------------------------

    async def process_article(self, article_id: str) -> bool:
        """Process a single article through the LLM pipeline.

        1. Load article from DB
        2. Call LLM to extract structured fields
        3. Generate embedding
        4. Update article in DB

        Returns True on success, False on failure.
        """
        logger.info(f"Processing article: {article_id}")

        # --- Load article ---------------------------------------------------
        async with get_session() as session:
            result = await session.execute(
                select(Article).where(Article.id == article_id)
            )
            article = result.scalar_one_or_none()

            if article is None:
                logger.error(f"Article not found: {article_id}")
                return False

            title = article.title
            body_text = article.body_text or ""

        if not body_text:
            logger.warning(f"Article has no body_text, skipping: {article_id}")
            await self._mark_failed(article_id, "No body_text available")
            return False

        # --- Mark as processing ---------------------------------------------
        await self._set_status(article_id, "processing")

        try:
            # --- LLM structured extraction ----------------------------------
            user_prompt = ARTICLE_ANALYSIS_USER_PROMPT.format(
                title=title,
                body_text=body_text[:12000],  # Truncate to stay within context window
            )
            raw_response = await self._call_chat(
                ARTICLE_ANALYSIS_SYSTEM_PROMPT, user_prompt
            )
            extracted = self._parse_llm_json(raw_response)
            validated = self._validate_extracted(extracted)

            # --- Embedding --------------------------------------------------
            embed_input = f"{title}\n\n{body_text[:2000]}"
            embedding = await self.generate_embedding(embed_input)

            # --- Persist to DB ----------------------------------------------
            async with get_session() as session:
                update_values = {
                    **validated,
                    "embedding": embedding,
                    "processing_status": "completed",
                    "llm_processed": True,
                }
                await session.execute(
                    update(Article)
                    .where(Article.id == article_id)
                    .values(**update_values)
                )

            logger.info(
                f"Article processed successfully: {article_id} | "
                f"topic={validated.get('primary_topic')} "
                f"sentiment={validated.get('sentiment')}"
            )
            return True

        except httpx.HTTPStatusError as e:
            error_msg = f"LLM API HTTP error {e.response.status_code}: {e.response.text[:500]}"
            logger.error(f"Failed to process article {article_id}: {error_msg}")
            await self._mark_failed(article_id, error_msg)
            return False

        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse LLM JSON response: {e}"
            logger.error(f"Failed to process article {article_id}: {error_msg}")
            await self._mark_failed(article_id, error_msg)
            return False

        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)[:500]}"
            logger.error(
                f"Failed to process article {article_id}: {error_msg}",
                exc_info=True,
            )
            await self._mark_failed(article_id, error_msg)
            return False

    async def process_pending_batch(self, batch_size: int | None = None) -> dict:
        """Process a batch of pending articles.

        Fetches up to `batch_size` articles with processing_status='pending',
        processes each one sequentially (respecting rate limits), and returns
        a summary dict with counts.
        """
        batch_size = batch_size or llm_settings.llm_batch_size

        # Fetch pending article IDs
        async with get_session() as session:
            result = await session.execute(
                select(Article.id)
                .where(Article.processing_status == "pending")
                .where(Article.body_text.isnot(None))
                .order_by(Article.fetched_at.desc())
                .limit(batch_size)
            )
            article_ids = [row[0] for row in result.fetchall()]

        if not article_ids:
            logger.info("No pending articles to process")
            return {"total": 0, "success": 0, "failed": 0}

        logger.info(f"Processing batch of {len(article_ids)} pending articles")

        success = 0
        failed = 0

        for article_id in article_ids:
            ok = await self.process_article(article_id)
            if ok:
                success += 1
            else:
                failed += 1

        summary = {
            "total": len(article_ids),
            "success": success,
            "failed": failed,
        }
        logger.info(
            f"Batch complete: total={summary['total']}, "
            f"success={summary['success']}, failed={summary['failed']}"
        )
        return summary

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------

    async def _set_status(self, article_id: str, status: str):
        """Update the processing_status for an article."""
        async with get_session() as session:
            await session.execute(
                update(Article)
                .where(Article.id == article_id)
                .values(processing_status=status)
            )

    async def _mark_failed(self, article_id: str, error_msg: str):
        """Mark an article as failed and store a truncated error in raw_metadata."""
        async with get_session() as session:
            # Fetch existing raw_metadata to preserve it
            result = await session.execute(
                select(Article.raw_metadata).where(Article.id == article_id)
            )
            raw_metadata = result.scalar_one_or_none() or {}

            raw_metadata["llm_error"] = error_msg[:1000]

            await session.execute(
                update(Article)
                .where(Article.id == article_id)
                .values(
                    processing_status="failed",
                    llm_processed=False,
                    raw_metadata=raw_metadata,
                )
            )
