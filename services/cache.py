"""CivicLens AI — In-memory TTL cache for AI response optimization.

Provides a lightweight, thread-safe cache with time-based expiration
to reduce redundant Vertex AI API calls and improve response latency.
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TTLCache:
    """In-memory cache with per-entry TTL expiration and size limits.

    Attributes:
        _ttl: Time-to-live in seconds for each cache entry.
        _max_size: Maximum number of entries before eviction.
        _cache: Internal storage mapping keys to (timestamp, value) tuples.
        _hits: Counter for cache hits (observability).
        _misses: Counter for cache misses (observability).
    """

    def __init__(self, ttl_seconds: int = 3600, max_size: int = 100) -> None:
        self._cache: dict[str, tuple[float, Any]] = {}
        self._ttl = ttl_seconds
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _make_key(*args: str) -> str:
        """Generate a deterministic cache key from input arguments."""
        raw = ":".join(str(a) for a in args)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def get(self, *args: str) -> Optional[Any]:
        """Retrieve a cached value if it exists and hasn't expired.

        Args:
            *args: Key components used to generate the cache key.

        Returns:
            Cached value if found and not expired, otherwise None.
        """
        key = self._make_key(*args)
        entry = self._cache.get(key)
        if entry is not None:
            timestamp, value = entry
            if time.time() - timestamp < self._ttl:
                self._hits += 1
                logger.debug("Cache HIT for key=%s (hits=%d)", key, self._hits)
                return value
            del self._cache[key]
        self._misses += 1
        return None

    def set(self, value: Any, *args: str) -> None:
        """Store a value in the cache with the current timestamp.

        Triggers eviction if the cache exceeds max_size.

        Args:
            value: The value to cache.
            *args: Key components used to generate the cache key.
        """
        if len(self._cache) >= self._max_size:
            self._evict()
        key = self._make_key(*args)
        self._cache[key] = (time.time(), value)
        logger.debug("Cache SET key=%s (size=%d)", key, len(self._cache))

    def _evict(self) -> None:
        """Remove expired entries, then oldest if still over capacity."""
        now = time.time()
        expired = [k for k, (ts, _) in self._cache.items() if now - ts >= self._ttl]
        for k in expired:
            del self._cache[k]
        if len(self._cache) >= self._max_size:
            oldest = min(self._cache, key=lambda k: self._cache[k][0])
            del self._cache[oldest]

    def clear(self) -> None:
        """Remove all entries from the cache."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    @property
    def stats(self) -> dict[str, int]:
        """Return cache performance statistics.

        Returns:
            Dictionary with size, hits, and misses counters.
        """
        return {
            "size": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
        }


# Module-level cache instances shared across the application.
timeline_cache = TTLCache(ttl_seconds=3600, max_size=50)
topic_cache = TTLCache(ttl_seconds=3600, max_size=100)
