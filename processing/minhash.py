"""MinHash + LSH for content-level deduplication (Level 3).

Generates MinHash signatures from article body text and uses
Locality-Sensitive Hashing (LSH) for efficient approximate
nearest-neighbor lookup based on Jaccard similarity.
"""

import re
import struct
from hashlib import sha1

# Default parameters
NUM_PERM = 128  # Number of hash permutations
SHINGLE_SIZE = 5  # Character n-gram size
MAX_HASH = (1 << 32) - 1  # 2^32 - 1

# Pre-generated coefficients for hash functions (a*x + b mod p)
# Using a large prime > 2^32
_MERSENNE_PRIME = (1 << 61) - 1


def _generate_hash_params(num_perm: int, seed: int = 42) -> list[tuple[int, int]]:
    """Generate (a, b) pairs for universal hash functions.

    Uses deterministic seeding so the same parameters are always generated.
    """
    import random

    rng = random.Random(seed)
    params = []
    for _ in range(num_perm):
        a = rng.randint(1, _MERSENNE_PRIME - 1)
        b = rng.randint(0, _MERSENNE_PRIME - 1)
        params.append((a, b))
    return params


# Pre-compute hash parameters at module level for consistency
_HASH_PARAMS = _generate_hash_params(NUM_PERM)


def _shingle(text: str, k: int = SHINGLE_SIZE) -> set[str]:
    """Create character-level k-shingles from text.

    Args:
        text: Input text (will be lowercased and whitespace-normalized).
        k: Shingle size (default 5).

    Returns:
        Set of k-character shingles.
    """
    # Normalize: lowercase, collapse whitespace
    text = re.sub(r"\s+", " ", text.lower().strip())
    if len(text) < k:
        return {text} if text else set()
    return {text[i : i + k] for i in range(len(text) - k + 1)}


def _hash_shingle(shingle: str) -> int:
    """Hash a shingle to a 32-bit integer."""
    digest = sha1(shingle.encode("utf-8")).digest()
    return struct.unpack("<I", digest[:4])[0]


def compute_minhash(
    text: str | None,
    num_perm: int = NUM_PERM,
    shingle_size: int = SHINGLE_SIZE,
) -> list[int] | None:
    """Compute MinHash signature for the given text.

    Args:
        text: Input text to fingerprint.
        num_perm: Number of hash permutations (signature length).
        shingle_size: Character n-gram size for shingling.

    Returns:
        List of num_perm hash values (the MinHash signature),
        or None if text is empty/too short.
    """
    if not text or not text.strip():
        return None

    shingles = _shingle(text, shingle_size)
    if not shingles:
        return None

    # Hash all shingles to integers
    hashed_shingles = [_hash_shingle(s) for s in shingles]

    # Compute MinHash: for each permutation, find the minimum hash
    params = _HASH_PARAMS[:num_perm]
    signature = []
    for a, b in params:
        min_val = MAX_HASH
        for h in hashed_shingles:
            # Universal hash: (a * h + b) mod prime mod max_hash
            val = ((a * h + b) % _MERSENNE_PRIME) & MAX_HASH
            if val < min_val:
                min_val = val
        signature.append(min_val)

    return signature


def jaccard_from_minhash(sig1: list[int], sig2: list[int]) -> float:
    """Estimate Jaccard similarity from two MinHash signatures.

    Args:
        sig1: First MinHash signature.
        sig2: Second MinHash signature.

    Returns:
        Estimated Jaccard similarity (0.0 to 1.0).

    Raises:
        ValueError: If signatures have different lengths.
    """
    if len(sig1) != len(sig2):
        raise ValueError(
            f"Signature lengths differ: {len(sig1)} vs {len(sig2)}"
        )
    matches = sum(1 for a, b in zip(sig1, sig2) if a == b)
    return matches / len(sig1)


def is_near_duplicate(
    sig1: list[int] | None,
    sig2: list[int] | None,
    threshold: float = 0.5,
) -> bool:
    """Check if two MinHash signatures indicate near-duplicate content.

    Args:
        sig1: First MinHash signature.
        sig2: Second MinHash signature.
        threshold: Minimum Jaccard similarity to consider duplicate (default 0.5).

    Returns:
        True if estimated Jaccard similarity >= threshold.
    """
    if sig1 is None or sig2 is None:
        return False
    return jaccard_from_minhash(sig1, sig2) >= threshold


class LSHIndex:
    """Locality-Sensitive Hashing index for fast approximate lookup.

    Divides MinHash signatures into bands. Two documents are candidate
    pairs if they share at least one identical band.

    Args:
        num_bands: Number of bands to divide signature into.
        rows_per_band: Number of rows (hash values) per band.
    """

    def __init__(self, num_bands: int = 16, rows_per_band: int = 8):
        if num_bands * rows_per_band > NUM_PERM:
            raise ValueError(
                f"num_bands * rows_per_band ({num_bands * rows_per_band}) "
                f"exceeds NUM_PERM ({NUM_PERM})"
            )
        self.num_bands = num_bands
        self.rows_per_band = rows_per_band
        # Each band has a dict mapping band_hash -> set of article_ids
        self._buckets: list[dict[int, set[str]]] = [
            {} for _ in range(num_bands)
        ]
        # Store full signatures for Jaccard verification
        self._signatures: dict[str, list[int]] = {}

    def insert(self, article_id: str, signature: list[int]) -> None:
        """Insert a document's MinHash signature into the index."""
        self._signatures[article_id] = signature
        for band_idx in range(self.num_bands):
            start = band_idx * self.rows_per_band
            end = start + self.rows_per_band
            band = tuple(signature[start:end])
            band_hash = hash(band)
            bucket = self._buckets[band_idx]
            if band_hash not in bucket:
                bucket[band_hash] = set()
            bucket[band_hash].add(article_id)

    def query(
        self,
        signature: list[int],
        threshold: float = 0.5,
        exclude_id: str | None = None,
    ) -> list[tuple[str, float]]:
        """Find near-duplicate candidates for the given signature.

        Args:
            signature: MinHash signature to query.
            threshold: Minimum Jaccard similarity for results.
            exclude_id: Article ID to exclude from results (e.g., self).

        Returns:
            List of (article_id, jaccard_similarity) sorted by similarity desc.
        """
        candidates: set[str] = set()
        for band_idx in range(self.num_bands):
            start = band_idx * self.rows_per_band
            end = start + self.rows_per_band
            band = tuple(signature[start:end])
            band_hash = hash(band)
            bucket = self._buckets[band_idx]
            if band_hash in bucket:
                candidates.update(bucket[band_hash])

        if exclude_id:
            candidates.discard(exclude_id)

        # Verify candidates with full Jaccard estimation
        results = []
        for cid in candidates:
            jaccard = jaccard_from_minhash(signature, self._signatures[cid])
            if jaccard >= threshold:
                results.append((cid, jaccard))

        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def __len__(self) -> int:
        return len(self._signatures)

    def __contains__(self, article_id: str) -> bool:
        return article_id in self._signatures
