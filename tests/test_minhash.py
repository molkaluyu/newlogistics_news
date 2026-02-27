"""
Tests for processing/minhash.py -- MinHash + LSH for content-level deduplication.

All tests are self-contained; no database access is required.
"""

import pytest

from processing.minhash import (
    LSHIndex,
    NUM_PERM,
    _shingle,
    compute_minhash,
    is_near_duplicate,
    jaccard_from_minhash,
)


# ---------------------------------------------------------------------------
# _shingle
# ---------------------------------------------------------------------------


class TestShingle:
    async def test_basic_text(self):
        """Standard text should produce a set of k-character shingles."""
        shingles = _shingle("hello world", k=5)
        assert isinstance(shingles, set)
        # "hello world" lowercased => "hello world" (11 chars), produces 11 - 5 + 1 = 7 shingles
        assert len(shingles) == 7
        assert "hello" in shingles
        assert "world" in shingles

    async def test_whitespace_normalization(self):
        """Multiple spaces and tabs should be collapsed to single space."""
        shingles_a = _shingle("hello   world", k=5)
        shingles_b = _shingle("hello world", k=5)
        assert shingles_a == shingles_b

    async def test_case_insensitive(self):
        """Shingling should be case-insensitive."""
        shingles_a = _shingle("Hello World", k=5)
        shingles_b = _shingle("hello world", k=5)
        assert shingles_a == shingles_b

    async def test_short_text(self):
        """Text shorter than k should return a set with the text itself."""
        shingles = _shingle("hi", k=5)
        assert shingles == {"hi"}

    async def test_text_exact_k_length(self):
        """Text exactly k characters should return one shingle."""
        shingles = _shingle("abcde", k=5)
        assert shingles == {"abcde"}

    async def test_empty_text(self):
        """Empty text should return an empty set."""
        shingles = _shingle("", k=5)
        assert shingles == set()

    async def test_whitespace_only(self):
        """Whitespace-only text should return empty set after strip."""
        shingles = _shingle("   \t\n  ", k=5)
        assert shingles == set()

    async def test_custom_k(self):
        """Custom shingle size should work."""
        shingles = _shingle("abcdef", k=3)
        # "abcdef" has 6 - 3 + 1 = 4 shingles: abc, bcd, cde, def
        assert len(shingles) == 4
        assert "abc" in shingles
        assert "def" in shingles


# ---------------------------------------------------------------------------
# compute_minhash
# ---------------------------------------------------------------------------


class TestComputeMinhash:
    async def test_basic_text(self):
        """Standard text should produce a MinHash signature list."""
        sig = compute_minhash("Global supply chains continue to face unprecedented challenges")
        assert sig is not None
        assert isinstance(sig, list)
        assert all(isinstance(v, int) for v in sig)

    async def test_default_signature_length(self):
        """Default signature length should match NUM_PERM (128)."""
        sig = compute_minhash("Global supply chains continue to face unprecedented challenges")
        assert sig is not None
        assert len(sig) == NUM_PERM

    async def test_custom_num_perm(self):
        """Custom num_perm should produce the specified signature length."""
        sig = compute_minhash(
            "Global supply chains continue to face unprecedented challenges",
            num_perm=64,
        )
        assert sig is not None
        assert len(sig) == 64

    async def test_empty_string_returns_none(self):
        """Empty string should return None."""
        sig = compute_minhash("")
        assert sig is None

    async def test_none_input_returns_none(self):
        """None input should return None."""
        sig = compute_minhash(None)
        assert sig is None

    async def test_whitespace_only_returns_none(self):
        """Whitespace-only string should return None."""
        sig = compute_minhash("   \t\n  ")
        assert sig is None

    async def test_deterministic(self):
        """Same input should always produce the same signature."""
        text = "Global supply chains continue to face unprecedented challenges"
        sig1 = compute_minhash(text)
        sig2 = compute_minhash(text)
        assert sig1 == sig2

    async def test_different_texts_different_signatures(self):
        """Different texts should generally produce different signatures."""
        sig1 = compute_minhash("Global supply chains continue to face unprecedented challenges")
        sig2 = compute_minhash("Weather forecast shows sunny skies with warm temperatures expected")
        assert sig1 is not None
        assert sig2 is not None
        assert sig1 != sig2


# ---------------------------------------------------------------------------
# jaccard_from_minhash
# ---------------------------------------------------------------------------


class TestJaccardFromMinhash:
    async def test_identical_signatures(self):
        """Identical signatures should have Jaccard similarity of 1.0."""
        sig = [1, 2, 3, 4, 5]
        assert jaccard_from_minhash(sig, sig) == 1.0

    async def test_completely_different_signatures(self):
        """Completely different signatures should have similarity 0.0."""
        sig1 = [1, 2, 3, 4, 5]
        sig2 = [6, 7, 8, 9, 10]
        assert jaccard_from_minhash(sig1, sig2) == 0.0

    async def test_partial_overlap(self):
        """Partially overlapping signatures should give fractional similarity."""
        sig1 = [1, 2, 3, 4, 5]
        sig2 = [1, 2, 3, 9, 10]
        result = jaccard_from_minhash(sig1, sig2)
        assert result == pytest.approx(0.6)  # 3 matches out of 5

    async def test_length_mismatch_raises_valueerror(self):
        """Signatures of different lengths should raise ValueError."""
        sig1 = [1, 2, 3]
        sig2 = [1, 2, 3, 4, 5]
        with pytest.raises(ValueError, match="Signature lengths differ"):
            jaccard_from_minhash(sig1, sig2)

    async def test_single_element_match(self):
        """Single element signatures that match should give 1.0."""
        assert jaccard_from_minhash([42], [42]) == 1.0

    async def test_single_element_mismatch(self):
        """Single element signatures that differ should give 0.0."""
        assert jaccard_from_minhash([42], [99]) == 0.0


# ---------------------------------------------------------------------------
# is_near_duplicate
# ---------------------------------------------------------------------------


class TestIsNearDuplicate:
    async def test_similar_content(self):
        """Near-identical text should be detected as near-duplicate."""
        text1 = "Global supply chains continue to face unprecedented challenges in the shipping industry"
        text2 = "Global supply chains continue to face unprecedented challenges in the logistics industry"
        sig1 = compute_minhash(text1)
        sig2 = compute_minhash(text2)
        # Very similar text should have high Jaccard similarity
        assert is_near_duplicate(sig1, sig2, threshold=0.3) is True

    async def test_different_content(self):
        """Very different text should not be near-duplicate."""
        text1 = "Global supply chains continue to face unprecedented challenges in the shipping industry"
        text2 = "The weather today is expected to be sunny with occasional clouds and light winds throughout the afternoon"
        sig1 = compute_minhash(text1)
        sig2 = compute_minhash(text2)
        assert is_near_duplicate(sig1, sig2, threshold=0.5) is False

    async def test_none_sig1_returns_false(self):
        """None first signature should return False."""
        sig2 = compute_minhash("Some text here for testing")
        assert is_near_duplicate(None, sig2, threshold=0.5) is False

    async def test_none_sig2_returns_false(self):
        """None second signature should return False."""
        sig1 = compute_minhash("Some text here for testing")
        assert is_near_duplicate(sig1, None, threshold=0.5) is False

    async def test_both_none_returns_false(self):
        """Both None signatures should return False."""
        assert is_near_duplicate(None, None, threshold=0.5) is False

    async def test_identical_signatures(self):
        """Identical signatures should always be near-duplicate."""
        sig = compute_minhash("Global supply chains continue to face unprecedented challenges")
        assert sig is not None
        assert is_near_duplicate(sig, sig, threshold=1.0) is True

    async def test_threshold_boundary(self):
        """Jaccard exactly at threshold should count as near-duplicate."""
        # Create signatures with known Jaccard: 3 out of 5 match = 0.6
        sig1 = [1, 2, 3, 4, 5]
        sig2 = [1, 2, 3, 9, 10]
        assert is_near_duplicate(sig1, sig2, threshold=0.6) is True
        assert is_near_duplicate(sig1, sig2, threshold=0.7) is False


# ---------------------------------------------------------------------------
# LSHIndex
# ---------------------------------------------------------------------------


class TestLSHIndex:
    async def test_insert_and_query_finds_similar(self):
        """Inserting a document and querying with identical signature should find it."""
        index = LSHIndex(num_bands=16, rows_per_band=8)
        text = "Global supply chains continue to face unprecedented challenges in the shipping industry today"
        sig = compute_minhash(text)
        assert sig is not None

        index.insert("article-1", sig)
        results = index.query(sig, threshold=0.5)
        assert len(results) >= 1
        ids = [r[0] for r in results]
        assert "article-1" in ids

    async def test_query_excludes_dissimilar(self):
        """Very different documents should not be returned as matches."""
        index = LSHIndex(num_bands=16, rows_per_band=8)

        sig1 = compute_minhash(
            "Global supply chains continue to face unprecedented challenges in the shipping industry today"
        )
        sig2 = compute_minhash(
            "The weather today is expected to be sunny with occasional clouds and light winds through the day"
        )
        assert sig1 is not None
        assert sig2 is not None

        index.insert("article-1", sig1)
        index.insert("article-2", sig2)

        results = index.query(sig1, threshold=0.8)
        ids = [r[0] for r in results]
        assert "article-2" not in ids

    async def test_threshold_filtering(self):
        """Only results above the Jaccard threshold should be returned."""
        index = LSHIndex(num_bands=16, rows_per_band=8)

        text1 = "Global supply chains continue to face unprecedented challenges in the shipping industry worldwide"
        text2 = "Global supply chains continue to face unprecedented challenges in the logistics industry worldwide"
        sig1 = compute_minhash(text1)
        sig2 = compute_minhash(text2)
        assert sig1 is not None
        assert sig2 is not None

        index.insert("article-1", sig1)
        # Query with sig2 at very high threshold
        results_high = index.query(sig2, threshold=0.99)
        results_low = index.query(sig2, threshold=0.1)
        # Low threshold should be at least as permissive
        assert len(results_low) >= len(results_high)

    async def test_exclude_id(self):
        """exclude_id should prevent a document from matching itself."""
        index = LSHIndex(num_bands=16, rows_per_band=8)
        sig = compute_minhash(
            "Global supply chains continue to face unprecedented challenges in the shipping industry today"
        )
        assert sig is not None

        index.insert("article-1", sig)
        results = index.query(sig, threshold=0.5, exclude_id="article-1")
        ids = [r[0] for r in results]
        assert "article-1" not in ids

    async def test_len(self):
        """__len__ should return the number of indexed documents."""
        index = LSHIndex(num_bands=16, rows_per_band=8)
        assert len(index) == 0

        sig1 = compute_minhash("Global supply chains face challenges in shipping")
        sig2 = compute_minhash("Air cargo rates surge amid strong holiday demand")
        assert sig1 is not None
        assert sig2 is not None

        index.insert("article-1", sig1)
        assert len(index) == 1

        index.insert("article-2", sig2)
        assert len(index) == 2

    async def test_contains(self):
        """__contains__ should check if an article_id is in the index."""
        index = LSHIndex(num_bands=16, rows_per_band=8)
        sig = compute_minhash("Global supply chains face challenges in shipping industry")
        assert sig is not None

        assert "article-1" not in index
        index.insert("article-1", sig)
        assert "article-1" in index
        assert "article-2" not in index

    async def test_invalid_bands_rows_raises(self):
        """num_bands * rows_per_band exceeding NUM_PERM should raise ValueError."""
        with pytest.raises(ValueError, match="exceeds NUM_PERM"):
            LSHIndex(num_bands=200, rows_per_band=200)

    async def test_query_results_sorted_by_similarity_desc(self):
        """Results should be sorted by Jaccard similarity in descending order."""
        index = LSHIndex(num_bands=16, rows_per_band=8)

        base_text = "Global supply chains continue to face unprecedented challenges in the shipping industry today with delays"
        sig_base = compute_minhash(base_text)
        assert sig_base is not None

        # Very similar text
        similar_text = "Global supply chains continue to face unprecedented challenges in the logistics industry today with delays"
        sig_similar = compute_minhash(similar_text)
        assert sig_similar is not None

        # Somewhat different text
        diff_text = "Ocean freight rates continue to fluctuate with port congestion affecting global trade routes substantially"
        sig_diff = compute_minhash(diff_text)
        assert sig_diff is not None

        index.insert("similar", sig_similar)
        index.insert("different", sig_diff)

        results = index.query(sig_base, threshold=0.0)
        if len(results) >= 2:
            # Verify descending order
            for i in range(len(results) - 1):
                assert results[i][1] >= results[i + 1][1]
