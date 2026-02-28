"""SimHash fingerprinting for title-level deduplication (Level 2).

Generates 64-bit SimHash fingerprints from text, enabling fast
approximate matching via Hamming distance comparison.
"""

import re
import struct
from collections.abc import Iterable
from hashlib import md5


def _tokenize(text: str) -> list[str]:
    """Tokenize text into word-level tokens.

    For CJK characters, each character becomes a token.
    For alphabetic text, words are extracted and lowercased.
    """
    tokens: list[str] = []
    # Extract CJK characters individually
    cjk = re.findall(r"[\u4e00-\u9fff\u3400-\u4dbf]", text)
    tokens.extend(cjk)
    # Extract alphabetic words (2+ chars)
    words = re.findall(r"[a-zA-Z]{2,}", text)
    tokens.extend(w.lower() for w in words)
    return tokens


def _hash_token(token: str) -> int:
    """Hash a single token to a 64-bit integer using MD5."""
    digest = md5(token.encode("utf-8")).digest()
    return struct.unpack("<Q", digest[:8])[0]


def compute_simhash(text: str | None, hashbits: int = 64) -> int | None:
    """Compute SimHash fingerprint for the given text.

    Args:
        text: Input text to fingerprint.
        hashbits: Number of bits in the fingerprint (default 64).

    Returns:
        64-bit integer fingerprint, or None if text is empty.
    """
    if not text or not text.strip():
        return None

    tokens = _tokenize(text)
    if not tokens:
        return None

    # Weighted vector (all weights = 1 for simplicity)
    v = [0] * hashbits
    for token in tokens:
        h = _hash_token(token)
        for i in range(hashbits):
            if h & (1 << i):
                v[i] += 1
            else:
                v[i] -= 1

    # Build fingerprint
    fingerprint = 0
    for i in range(hashbits):
        if v[i] > 0:
            fingerprint |= 1 << i

    return fingerprint


def hamming_distance(hash1: int, hash2: int) -> int:
    """Compute Hamming distance between two 64-bit SimHash values."""
    return bin(hash1 ^ hash2).count("1")


def is_similar(hash1: int | None, hash2: int | None, threshold: int = 3) -> bool:
    """Check if two SimHash values are similar (Hamming distance <= threshold).

    Args:
        hash1: First SimHash fingerprint.
        hash2: Second SimHash fingerprint.
        threshold: Maximum Hamming distance to consider similar (default 3).

    Returns:
        True if hashes are within threshold distance, False otherwise.
    """
    if hash1 is None or hash2 is None:
        return False
    return hamming_distance(hash1, hash2) <= threshold


def find_similar(
    target_hash: int,
    candidates: Iterable[tuple[str, int]],
    threshold: int = 3,
) -> list[tuple[str, int]]:
    """Find all candidate entries similar to target hash.

    Args:
        target_hash: The SimHash to compare against.
        candidates: Iterable of (article_id, simhash_value) tuples.
        threshold: Maximum Hamming distance.

    Returns:
        List of (article_id, hamming_distance) tuples for matches.
    """
    matches = []
    for article_id, candidate_hash in candidates:
        dist = hamming_distance(target_hash, candidate_hash)
        if dist <= threshold:
            matches.append((article_id, dist))
    return matches
