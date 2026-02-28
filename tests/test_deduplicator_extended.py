"""
Tests for processing/deduplicator.py -- Level 2 (SimHash) and Level 3 (MinHash)
deduplication methods, plus the combined check_all_levels.

All database access is mocked; no real PostgreSQL connection is needed.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from processing.deduplicator import Deduplicator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_get_session(mock_session):
    """Create a patched get_session that yields mock_session."""
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _fake():
        yield mock_session

    return _fake


def _make_row(**kwargs):
    """Create a MagicMock that acts like a SQLAlchemy Row with attribute access."""
    row = MagicMock()
    for key, value in kwargs.items():
        setattr(row, key, value)
    return row


# ---------------------------------------------------------------------------
# find_simhash_duplicates
# ---------------------------------------------------------------------------


class TestFindSimhashDuplicates:
    async def test_finds_matches_within_threshold(self):
        """Articles with simhash within Hamming distance should be returned."""
        mock_session = AsyncMock()
        mock_result = MagicMock()

        # Target simhash = 0b1010, row simhash = 0b1011 -> distance 1
        row = _make_row(
            id="article-1",
            title="Supply chain crisis",
            url="https://example.com/article-1",
            title_simhash=0b1011,
        )
        mock_result.fetchall.return_value = [row]
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "processing.deduplicator.get_session",
            new=_make_fake_get_session(mock_session),
        ):
            dedup = Deduplicator(simhash_threshold=3)
            matches = await dedup.find_simhash_duplicates(0b1010)

        assert len(matches) == 1
        assert matches[0]["id"] == "article-1"
        assert matches[0]["hamming_distance"] == 1

    async def test_no_matches_beyond_threshold(self):
        """Articles with simhash beyond threshold should not be returned."""
        mock_session = AsyncMock()
        mock_result = MagicMock()

        # Target = 0b11110000, row = 0b00001111 -> distance 8
        row = _make_row(
            id="article-1",
            title="Different article",
            url="https://example.com/article-1",
            title_simhash=0b00001111,
        )
        mock_result.fetchall.return_value = [row]
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "processing.deduplicator.get_session",
            new=_make_fake_get_session(mock_session),
        ):
            dedup = Deduplicator(simhash_threshold=3)
            matches = await dedup.find_simhash_duplicates(0b11110000)

        assert matches == []

    async def test_no_rows_in_db(self):
        """When there are no articles with simhashes, return empty list."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "processing.deduplicator.get_session",
            new=_make_fake_get_session(mock_session),
        ):
            dedup = Deduplicator(simhash_threshold=3)
            matches = await dedup.find_simhash_duplicates(0b1010)

        assert matches == []

    async def test_excludes_id(self):
        """When exclude_id is provided, the query should exclude that article."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "processing.deduplicator.get_session",
            new=_make_fake_get_session(mock_session),
        ):
            dedup = Deduplicator(simhash_threshold=3)
            matches = await dedup.find_simhash_duplicates(
                0b1010, exclude_id="self-id"
            )

        assert matches == []
        mock_session.execute.assert_called_once()

    async def test_multiple_matches(self):
        """Multiple articles within threshold should all be returned."""
        mock_session = AsyncMock()
        mock_result = MagicMock()

        rows = [
            _make_row(
                id="article-1",
                title="Crisis one",
                url="https://example.com/1",
                title_simhash=0b1011,  # distance 1 from 0b1010
            ),
            _make_row(
                id="article-2",
                title="Crisis two",
                url="https://example.com/2",
                title_simhash=0b1010,  # distance 0 from 0b1010
            ),
        ]
        mock_result.fetchall.return_value = rows
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "processing.deduplicator.get_session",
            new=_make_fake_get_session(mock_session),
        ):
            dedup = Deduplicator(simhash_threshold=3)
            matches = await dedup.find_simhash_duplicates(0b1010)

        assert len(matches) == 2
        ids = [m["id"] for m in matches]
        assert "article-1" in ids
        assert "article-2" in ids

    async def test_returns_expected_dict_keys(self):
        """Each match dict should have id, title, url, hamming_distance keys."""
        mock_session = AsyncMock()
        mock_result = MagicMock()

        row = _make_row(
            id="article-1",
            title="Supply chain crisis",
            url="https://example.com/article-1",
            title_simhash=0b1010,
        )
        mock_result.fetchall.return_value = [row]
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "processing.deduplicator.get_session",
            new=_make_fake_get_session(mock_session),
        ):
            dedup = Deduplicator(simhash_threshold=3)
            matches = await dedup.find_simhash_duplicates(0b1010)

        assert len(matches) == 1
        assert set(matches[0].keys()) == {"id", "title", "url", "hamming_distance"}


# ---------------------------------------------------------------------------
# find_minhash_duplicates
# ---------------------------------------------------------------------------


class TestFindMinhashDuplicates:
    async def test_finds_matches_above_threshold(self):
        """Articles with Jaccard similarity >= threshold should be returned."""
        mock_session = AsyncMock()
        mock_result = MagicMock()

        # Identical signature = Jaccard 1.0
        sig = list(range(128))
        row = _make_row(
            id="article-1",
            title="Supply chain crisis",
            url="https://example.com/article-1",
            content_minhash=sig,
        )
        mock_result.fetchall.return_value = [row]
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "processing.deduplicator.get_session",
            new=_make_fake_get_session(mock_session),
        ):
            dedup = Deduplicator(minhash_threshold=0.5)
            matches = await dedup.find_minhash_duplicates(sig)

        assert len(matches) == 1
        assert matches[0]["id"] == "article-1"
        assert matches[0]["jaccard_similarity"] == 1.0

    async def test_no_matches_below_threshold(self):
        """Articles with Jaccard similarity below threshold should not be returned."""
        mock_session = AsyncMock()
        mock_result = MagicMock()

        # Completely different signatures = Jaccard 0.0
        sig_query = list(range(128))
        sig_db = list(range(128, 256))
        row = _make_row(
            id="article-1",
            title="Different article",
            url="https://example.com/article-1",
            content_minhash=sig_db,
        )
        mock_result.fetchall.return_value = [row]
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "processing.deduplicator.get_session",
            new=_make_fake_get_session(mock_session),
        ):
            dedup = Deduplicator(minhash_threshold=0.5)
            matches = await dedup.find_minhash_duplicates(sig_query)

        assert matches == []

    async def test_no_rows_in_db(self):
        """When there are no articles with minhashes, return empty list."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "processing.deduplicator.get_session",
            new=_make_fake_get_session(mock_session),
        ):
            dedup = Deduplicator(minhash_threshold=0.5)
            matches = await dedup.find_minhash_duplicates(list(range(128)))

        assert matches == []

    async def test_handles_valueerror_gracefully(self):
        """If a row's minhash has a different length, it should be skipped (not crash)."""
        mock_session = AsyncMock()
        mock_result = MagicMock()

        # Row has mismatched signature length (64 vs 128 in query)
        sig_query = list(range(128))
        row = _make_row(
            id="article-1",
            title="Bad signature article",
            url="https://example.com/article-1",
            content_minhash=list(range(64)),  # wrong length
        )
        mock_result.fetchall.return_value = [row]
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "processing.deduplicator.get_session",
            new=_make_fake_get_session(mock_session),
        ):
            dedup = Deduplicator(minhash_threshold=0.5)
            # Should not raise -- ValueError is caught internally
            matches = await dedup.find_minhash_duplicates(sig_query)

        assert matches == []

    async def test_returns_expected_dict_keys(self):
        """Each match dict should have id, title, url, jaccard_similarity keys."""
        mock_session = AsyncMock()
        mock_result = MagicMock()

        sig = list(range(128))
        row = _make_row(
            id="article-1",
            title="Supply chain crisis",
            url="https://example.com/article-1",
            content_minhash=sig,
        )
        mock_result.fetchall.return_value = [row]
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "processing.deduplicator.get_session",
            new=_make_fake_get_session(mock_session),
        ):
            dedup = Deduplicator(minhash_threshold=0.5)
            matches = await dedup.find_minhash_duplicates(sig)

        assert len(matches) == 1
        assert set(matches[0].keys()) == {"id", "title", "url", "jaccard_similarity"}

    async def test_excludes_id(self):
        """When exclude_id is provided, it should be passed to the query."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "processing.deduplicator.get_session",
            new=_make_fake_get_session(mock_session),
        ):
            dedup = Deduplicator(minhash_threshold=0.5)
            matches = await dedup.find_minhash_duplicates(
                list(range(128)), exclude_id="self-id"
            )

        assert matches == []
        mock_session.execute.assert_called_once()


# ---------------------------------------------------------------------------
# check_all_levels
# ---------------------------------------------------------------------------


class TestCheckAllLevels:
    async def test_url_duplicate_found(self):
        """When URL is a duplicate, is_duplicate should be True."""
        mock_session = AsyncMock()
        mock_result_url = MagicMock()
        mock_result_url.scalar_one_or_none.return_value = "existing-uuid"
        mock_session.execute = AsyncMock(return_value=mock_result_url)

        with patch(
            "processing.deduplicator.get_session",
            new=_make_fake_get_session(mock_session),
        ):
            dedup = Deduplicator()
            result = await dedup.check_all_levels(
                url="https://example.com/existing-article"
            )

        assert result["is_url_duplicate"] is True
        assert result["is_duplicate"] is True
        assert result["simhash_matches"] == []
        assert result["minhash_matches"] == []

    async def test_simhash_duplicate_found(self):
        """When URL is new but simhash matches exist, is_duplicate should be True."""
        mock_session = AsyncMock()

        # First call: URL check (not found)
        mock_result_url = MagicMock()
        mock_result_url.scalar_one_or_none.return_value = None

        # Second call: simhash check (match found)
        mock_result_simhash = MagicMock()
        row = _make_row(
            id="article-1",
            title="Similar title",
            url="https://example.com/similar",
            title_simhash=0b1011,
        )
        mock_result_simhash.fetchall.return_value = [row]

        mock_session.execute = AsyncMock(
            side_effect=[mock_result_url, mock_result_simhash]
        )

        with patch(
            "processing.deduplicator.get_session",
            new=_make_fake_get_session(mock_session),
        ):
            dedup = Deduplicator(simhash_threshold=3)
            result = await dedup.check_all_levels(
                url="https://example.com/new-article",
                title_simhash=0b1010,
            )

        assert result["is_url_duplicate"] is False
        assert len(result["simhash_matches"]) == 1
        assert result["minhash_matches"] == []
        assert result["is_duplicate"] is True

    async def test_minhash_duplicate_found(self):
        """When URL/simhash are clean but minhash matches, is_duplicate should be True."""
        mock_session = AsyncMock()

        # First call: URL check (not found)
        mock_result_url = MagicMock()
        mock_result_url.scalar_one_or_none.return_value = None

        # Second call: simhash check (no matches)
        mock_result_simhash = MagicMock()
        mock_result_simhash.fetchall.return_value = []

        # Third call: minhash check (match found)
        sig = list(range(128))
        mock_result_minhash = MagicMock()
        row = _make_row(
            id="article-2",
            title="Near-duplicate content",
            url="https://example.com/near-dup",
            content_minhash=sig,
        )
        mock_result_minhash.fetchall.return_value = [row]

        mock_session.execute = AsyncMock(
            side_effect=[mock_result_url, mock_result_simhash, mock_result_minhash]
        )

        with patch(
            "processing.deduplicator.get_session",
            new=_make_fake_get_session(mock_session),
        ):
            dedup = Deduplicator(simhash_threshold=3, minhash_threshold=0.5)
            result = await dedup.check_all_levels(
                url="https://example.com/new-article",
                title_simhash=0b1010,
                content_minhash=sig,
            )

        assert result["is_url_duplicate"] is False
        assert result["simhash_matches"] == []
        assert len(result["minhash_matches"]) == 1
        assert result["is_duplicate"] is True

    async def test_no_duplicates_at_any_level(self):
        """When no duplicates found at any level, is_duplicate should be False."""
        mock_session = AsyncMock()

        # URL check: not found
        mock_result_url = MagicMock()
        mock_result_url.scalar_one_or_none.return_value = None

        # Simhash check: no matches (far hashes)
        mock_result_simhash = MagicMock()
        row = _make_row(
            id="article-1",
            title="Unrelated article",
            url="https://example.com/unrelated",
            title_simhash=0b00001111,  # distance 8 from 0b11110000
        )
        mock_result_simhash.fetchall.return_value = [row]

        # Minhash check: no matches (different signatures)
        sig_query = list(range(128))
        sig_db = list(range(128, 256))
        mock_result_minhash = MagicMock()
        row2 = _make_row(
            id="article-1",
            title="Unrelated article",
            url="https://example.com/unrelated",
            content_minhash=sig_db,
        )
        mock_result_minhash.fetchall.return_value = [row2]

        mock_session.execute = AsyncMock(
            side_effect=[mock_result_url, mock_result_simhash, mock_result_minhash]
        )

        with patch(
            "processing.deduplicator.get_session",
            new=_make_fake_get_session(mock_session),
        ):
            dedup = Deduplicator(simhash_threshold=3, minhash_threshold=0.5)
            result = await dedup.check_all_levels(
                url="https://example.com/unique-article",
                title_simhash=0b11110000,
                content_minhash=sig_query,
            )

        assert result["is_url_duplicate"] is False
        assert result["simhash_matches"] == []
        assert result["minhash_matches"] == []
        assert result["is_duplicate"] is False

    async def test_skips_simhash_when_none(self):
        """When title_simhash is None, simhash check should be skipped."""
        mock_session = AsyncMock()

        mock_result_url = MagicMock()
        mock_result_url.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result_url)

        with patch(
            "processing.deduplicator.get_session",
            new=_make_fake_get_session(mock_session),
        ):
            dedup = Deduplicator()
            result = await dedup.check_all_levels(
                url="https://example.com/new-article",
                title_simhash=None,
                content_minhash=None,
            )

        assert result["is_url_duplicate"] is False
        assert result["simhash_matches"] == []
        assert result["minhash_matches"] == []
        assert result["is_duplicate"] is False
        # Only one DB call (URL check), simhash and minhash skipped
        assert mock_session.execute.call_count == 1

    async def test_skips_minhash_when_none(self):
        """When content_minhash is None, minhash check should be skipped."""
        mock_session = AsyncMock()

        mock_result_url = MagicMock()
        mock_result_url.scalar_one_or_none.return_value = None

        mock_result_simhash = MagicMock()
        mock_result_simhash.fetchall.return_value = []

        mock_session.execute = AsyncMock(
            side_effect=[mock_result_url, mock_result_simhash]
        )

        with patch(
            "processing.deduplicator.get_session",
            new=_make_fake_get_session(mock_session),
        ):
            dedup = Deduplicator()
            result = await dedup.check_all_levels(
                url="https://example.com/new-article",
                title_simhash=0b1010,
                content_minhash=None,
            )

        assert result["minhash_matches"] == []
        # Two DB calls: URL + simhash, minhash skipped
        assert mock_session.execute.call_count == 2

    async def test_returns_expected_keys(self):
        """check_all_levels result should have all four expected keys."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "processing.deduplicator.get_session",
            new=_make_fake_get_session(mock_session),
        ):
            dedup = Deduplicator()
            result = await dedup.check_all_levels(
                url="https://example.com/article"
            )

        assert set(result.keys()) == {
            "is_url_duplicate",
            "simhash_matches",
            "minhash_matches",
            "is_duplicate",
        }
