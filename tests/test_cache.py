"""Unit tests for CivicLens TTL cache module."""

import time
from unittest.mock import patch

from services.cache import TTLCache


class TestTTLCache:
    """Test suite for the in-memory TTL cache."""

    def test_set_and_get(self):
        """Stored values should be retrievable."""
        cache = TTLCache(ttl_seconds=60)
        cache.set("hello", "key1")
        assert cache.get("key1") == "hello"

    def test_miss_returns_none(self):
        """Missing keys should return None."""
        cache = TTLCache(ttl_seconds=60)
        assert cache.get("nonexistent") is None

    def test_expired_entry_returns_none(self):
        """Expired entries should return None and be evicted."""
        cache = TTLCache(ttl_seconds=1)
        cache.set("value", "key1")
        with patch("services.cache.time") as mock_time:
            mock_time.time.return_value = time.time() + 2
            assert cache.get("key1") is None

    def test_max_size_eviction(self):
        """Cache should evict oldest entries when max_size is reached."""
        cache = TTLCache(ttl_seconds=3600, max_size=3)
        cache.set("a", "k1")
        cache.set("b", "k2")
        cache.set("c", "k3")
        cache.set("d", "k4")  # Should evict k1
        assert cache.get("k1") is None
        assert cache.get("k4") == "d"

    def test_clear(self):
        """Clear should remove all entries and reset stats."""
        cache = TTLCache(ttl_seconds=60)
        cache.set("v1", "k1")
        cache.set("v2", "k2")
        cache.clear()
        assert cache.get("k1") is None
        assert cache.stats["size"] == 0
        assert cache.stats["hits"] == 0

    def test_stats_tracking(self):
        """Stats should track hits and misses accurately."""
        cache = TTLCache(ttl_seconds=60)
        cache.set("val", "k1")
        cache.get("k1")  # hit
        cache.get("k1")  # hit
        cache.get("missing")  # miss
        stats = cache.stats
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["size"] == 1

    def test_deterministic_keys(self):
        """Same arguments should produce the same cache key."""
        key1 = TTLCache._make_key("hello", "world")
        key2 = TTLCache._make_key("hello", "world")
        assert key1 == key2

    def test_different_args_different_keys(self):
        """Different arguments should produce different keys."""
        key1 = TTLCache._make_key("hello")
        key2 = TTLCache._make_key("world")
        assert key1 != key2
