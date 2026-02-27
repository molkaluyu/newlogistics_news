"""
Tests for processing/simhash.py -- SimHash fingerprinting for title-level deduplication.

All tests are self-contained; no database access is required.
"""

import pytest

from processing.simhash import (
    _tokenize,
    compute_simhash,
    find_similar,
    hamming_distance,
    is_similar,
)


# ---------------------------------------------------------------------------
# _tokenize
# ---------------------------------------------------------------------------


class TestTokenize:
    async def test_english_words(self):
        """English words (2+ chars) should be lowercased and returned."""
        tokens = _tokenize("Supply Chain Crisis Deepens")
        assert "supply" in tokens
        assert "chain" in tokens
        assert "crisis" in tokens
        assert "deepens" in tokens

    async def test_single_char_words_excluded(self):
        """Single-character English words should be excluded (requires 2+ chars)."""
        tokens = _tokenize("I am a test")
        # 'I', 'a' are single chars and should be excluded
        assert "i" not in tokens
        assert "a" not in tokens
        assert "am" in tokens
        assert "test" in tokens

    async def test_cjk_characters(self):
        """CJK characters should each become an individual token."""
        tokens = _tokenize("\u4f9b\u5e94\u94fe\u5371\u673a")
        assert "\u4f9b" in tokens
        assert "\u5e94" in tokens
        assert "\u94fe" in tokens
        assert "\u5371" in tokens
        assert "\u673a" in tokens
        assert len(tokens) == 5

    async def test_mixed_text(self):
        """Mixed English and CJK text should produce tokens from both."""
        tokens = _tokenize("Supply chain \u4f9b\u5e94\u94fe crisis")
        assert "supply" in tokens
        assert "chain" in tokens
        assert "crisis" in tokens
        assert "\u4f9b" in tokens
        assert "\u5e94" in tokens
        assert "\u94fe" in tokens

    async def test_empty_string(self):
        """Empty string should return an empty list."""
        tokens = _tokenize("")
        assert tokens == []

    async def test_whitespace_only(self):
        """Whitespace-only string should return an empty list."""
        tokens = _tokenize("   \t\n  ")
        assert tokens == []

    async def test_numbers_and_punctuation_excluded(self):
        """Numbers and punctuation should not produce tokens."""
        tokens = _tokenize("123 !@# $%^")
        assert tokens == []


# ---------------------------------------------------------------------------
# compute_simhash
# ---------------------------------------------------------------------------


class TestComputeSimhash:
    async def test_basic_text(self):
        """Basic English text should produce an integer hash."""
        result = compute_simhash("Supply chain crisis deepens in global trade")
        assert isinstance(result, int)
        assert result >= 0

    async def test_cjk_text(self):
        """CJK text should produce an integer hash."""
        result = compute_simhash("\u5168\u7403\u4f9b\u5e94\u94fe\u5371\u673a\u52a0\u6df1")
        assert isinstance(result, int)
        assert result >= 0

    async def test_empty_string_returns_none(self):
        """Empty string should return None."""
        result = compute_simhash("")
        assert result is None

    async def test_none_input_returns_none(self):
        """None input should return None."""
        result = compute_simhash(None)
        assert result is None

    async def test_whitespace_only_returns_none(self):
        """Whitespace-only string should return None."""
        result = compute_simhash("   \t\n  ")
        assert result is None

    async def test_similar_titles_produce_close_hashes(self):
        """Similar titles should produce SimHash values with small Hamming distance."""
        hash1 = compute_simhash("Supply chain crisis deepens in global trade")
        hash2 = compute_simhash("Supply chain crisis deepens in world trade")
        assert hash1 is not None
        assert hash2 is not None
        distance = hamming_distance(hash1, hash2)
        # Similar titles should have small distance (well below 64)
        assert distance < 20

    async def test_different_titles_produce_different_hashes(self):
        """Very different titles should generally produce different hashes."""
        hash1 = compute_simhash("Supply chain crisis deepens in global trade")
        hash2 = compute_simhash("Weather forecast sunny skies tomorrow morning")
        assert hash1 is not None
        assert hash2 is not None
        # Different content should not be identical
        assert hash1 != hash2

    async def test_deterministic(self):
        """Same input should always produce the same hash."""
        text = "Supply chain crisis deepens"
        hash1 = compute_simhash(text)
        hash2 = compute_simhash(text)
        assert hash1 == hash2

    async def test_numbers_only_returns_none(self):
        """Text with only numbers (no 2+ char alpha words, no CJK) returns None."""
        result = compute_simhash("123 456 789")
        assert result is None


# ---------------------------------------------------------------------------
# hamming_distance
# ---------------------------------------------------------------------------


class TestHammingDistance:
    async def test_identical_hashes_zero_distance(self):
        """Identical hashes should have a Hamming distance of 0."""
        assert hamming_distance(0b1010, 0b1010) == 0
        assert hamming_distance(0, 0) == 0
        assert hamming_distance(0xFFFFFFFFFFFFFFFF, 0xFFFFFFFFFFFFFFFF) == 0

    async def test_known_distance_one_bit(self):
        """Hashes differing in one bit should have distance 1."""
        assert hamming_distance(0b1010, 0b1011) == 1

    async def test_known_distance_two_bits(self):
        """Hashes differing in two bits should have distance 2."""
        assert hamming_distance(0b1010, 0b1001) == 2

    async def test_known_distance_all_bits(self):
        """All bits different in a byte should give distance 8."""
        assert hamming_distance(0b00000000, 0b11111111) == 8

    async def test_large_values(self):
        """Should handle 64-bit values correctly."""
        h1 = 0xAAAAAAAAAAAAAAAA  # alternating 10101010...
        h2 = 0x5555555555555555  # alternating 01010101...
        # All 64 bits are different
        assert hamming_distance(h1, h2) == 64


# ---------------------------------------------------------------------------
# is_similar
# ---------------------------------------------------------------------------


class TestIsSimilar:
    async def test_within_threshold(self):
        """Hashes within threshold should be considered similar."""
        h1 = 0b1010
        h2 = 0b1011  # distance = 1
        assert is_similar(h1, h2, threshold=3) is True

    async def test_at_threshold_boundary(self):
        """Hashes exactly at threshold should be considered similar."""
        h1 = 0b1010
        h2 = 0b0101  # distance = 4 (all 4 lowest bits differ)
        assert is_similar(h1, h2, threshold=4) is True

    async def test_beyond_threshold(self):
        """Hashes beyond threshold should not be considered similar."""
        h1 = 0b11110000
        h2 = 0b00001111  # distance = 8
        assert is_similar(h1, h2, threshold=3) is False

    async def test_none_hash1_returns_false(self):
        """None first hash should return False."""
        assert is_similar(None, 12345, threshold=3) is False

    async def test_none_hash2_returns_false(self):
        """None second hash should return False."""
        assert is_similar(12345, None, threshold=3) is False

    async def test_both_none_returns_false(self):
        """Both None hashes should return False."""
        assert is_similar(None, None, threshold=3) is False

    async def test_identical_hashes_similar(self):
        """Identical hashes should always be similar (distance=0)."""
        assert is_similar(42, 42, threshold=0) is True

    async def test_default_threshold(self):
        """Default threshold of 3 should work correctly."""
        h1 = 0b1000
        h2 = 0b1001  # distance = 1
        assert is_similar(h1, h2) is True  # default threshold=3


# ---------------------------------------------------------------------------
# find_similar
# ---------------------------------------------------------------------------


class TestFindSimilar:
    async def test_finds_matching_candidates(self):
        """Should return candidates within the Hamming distance threshold."""
        target = 0b1010
        candidates = [
            ("article-1", 0b1011),  # distance 1 -- match
            ("article-2", 0b1010),  # distance 0 -- match
        ]
        matches = find_similar(target, candidates, threshold=3)
        assert len(matches) == 2
        ids = [m[0] for m in matches]
        assert "article-1" in ids
        assert "article-2" in ids

    async def test_excludes_far_candidates(self):
        """Should exclude candidates beyond the threshold."""
        target = 0b11110000
        candidates = [
            ("article-1", 0b11110001),  # distance 1 -- match
            ("article-2", 0b00001111),  # distance 8 -- too far
        ]
        matches = find_similar(target, candidates, threshold=3)
        assert len(matches) == 1
        assert matches[0][0] == "article-1"
        assert matches[0][1] == 1  # hamming distance

    async def test_empty_candidates(self):
        """Empty candidates should return empty list."""
        matches = find_similar(0b1010, [], threshold=3)
        assert matches == []

    async def test_returns_hamming_distance(self):
        """Returned tuples should include the correct Hamming distance."""
        target = 0b1010
        candidates = [("article-1", 0b1000)]  # distance 1
        matches = find_similar(target, candidates, threshold=3)
        assert len(matches) == 1
        assert matches[0] == ("article-1", 1)

    async def test_no_matches_returns_empty(self):
        """If no candidates are within threshold, return empty list."""
        target = 0b11110000
        candidates = [
            ("article-1", 0b00001111),  # distance 8
            ("article-2", 0b00000000),  # distance 4
        ]
        matches = find_similar(target, candidates, threshold=2)
        assert matches == []
