"""Redis cache service for caching embeddings, queries, and results."""

import hashlib
import json
import logging
from typing import Any

import redis
from redis.exceptions import ConnectionError, RedisError

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisCache:
    """Redis-based caching service for performance optimization."""

    def __init__(
        self,
        redis_url: str | None = None,
        enabled: bool | None = None,
    ) -> None:
        """
        Initialize Redis cache.

        Args:
            redis_url: Redis connection URL. Defaults to settings.redis_url.
            enabled: Whether caching is enabled. Defaults to settings.redis_enabled.
        """
        self.redis_url = redis_url or settings.redis_url
        self.enabled = enabled if enabled is not None else settings.redis_enabled
        self._client: redis.Redis | None = None

        if self.enabled:
            self._connect()

    def _connect(self) -> None:
        """Establish connection to Redis."""
        try:
            self._client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            # Test connection
            self._client.ping()
            logger.info(f"Connected to Redis at {self.redis_url}")
        except (ConnectionError, RedisError) as e:
            logger.warning(
                f"Failed to connect to Redis: {e}. Caching will be disabled."
            )
            self.enabled = False
            self._client = None

    @property
    def is_available(self) -> bool:
        """Check if Redis is available."""
        if not self.enabled or self._client is None:
            return False

        try:
            self._client.ping()
            return True
        except (ConnectionError, RedisError):
            return False

    def _generate_key(self, prefix: str, identifier: str) -> str:
        """
        Generate a cache key.

        Args:
            prefix: Key prefix (e.g., 'query', 'embedding').
            identifier: Unique identifier for the cached item.

        Returns:
            Cache key string.
        """
        # Hash the identifier to keep keys short and consistent
        hash_value = hashlib.sha256(identifier.encode()).hexdigest()[:16]
        return f"rag:{prefix}:{hash_value}"

    def get(self, prefix: str, identifier: str) -> Any | None:
        """
        Get a value from cache.

        Args:
            prefix: Key prefix.
            identifier: Unique identifier.

        Returns:
            Cached value or None if not found.
        """
        if not self.is_available:
            return None

        try:
            key = self._generate_key(prefix, identifier)
            value = self._client.get(key)

            if value:
                logger.debug(f"Cache hit for {prefix}: {identifier[:50]}...")
                return json.loads(value)
            else:
                logger.debug(f"Cache miss for {prefix}: {identifier[:50]}...")
                return None

        except (RedisError, json.JSONDecodeError) as e:
            logger.warning(f"Cache get error: {e}")
            return None

    def set(
        self,
        prefix: str,
        identifier: str,
        value: Any,
        ttl: int | None = None,
    ) -> bool:
        """
        Set a value in cache.

        Args:
            prefix: Key prefix.
            identifier: Unique identifier.
            value: Value to cache (must be JSON serializable).
            ttl: Time to live in seconds. If None, uses default for prefix.

        Returns:
            True if successful, False otherwise.
        """
        if not self.is_available:
            return False

        try:
            key = self._generate_key(prefix, identifier)
            serialized = json.dumps(value)

            # Use default TTL if not specified
            if ttl is None:
                ttl = self._get_default_ttl(prefix)

            self._client.setex(key, ttl, serialized)
            logger.debug(f"Cached {prefix}: {identifier[:50]}... (TTL: {ttl}s)")
            return True

        except (RedisError, TypeError) as e:
            logger.warning(f"Cache set error: {e}")
            return False

    def delete(self, prefix: str, identifier: str) -> bool:
        """
        Delete a value from cache.

        Args:
            prefix: Key prefix.
            identifier: Unique identifier.

        Returns:
            True if successful, False otherwise.
        """
        if not self.is_available:
            return False

        try:
            key = self._generate_key(prefix, identifier)
            self._client.delete(key)
            logger.debug(f"Deleted cache: {prefix}: {identifier[:50]}...")
            return True

        except RedisError as e:
            logger.warning(f"Cache delete error: {e}")
            return False

    def delete_pattern(self, prefix: str, pattern: str = "*") -> int:
        """
        Delete all keys matching a pattern.

        Args:
            prefix: Key prefix.
            pattern: Pattern to match (default: all keys with prefix).

        Returns:
            Number of keys deleted.
        """
        if not self.is_available:
            return 0

        try:
            full_pattern = f"rag:{prefix}:{pattern}"
            keys = list(self._client.scan_iter(match=full_pattern, count=100))

            if keys:
                deleted = self._client.delete(*keys)
                logger.info(f"Deleted {deleted} cache keys matching {full_pattern}")
                return deleted
            return 0

        except RedisError as e:
            logger.warning(f"Cache pattern delete error: {e}")
            return 0

    def invalidate_document_cache(self, document_id: str) -> None:
        """
        Invalidate all cache entries related to a document.

        This should be called when a document is updated or deleted.

        Args:
            document_id: The document ID.
        """
        if not self.is_available:
            return

        # Invalidate queries that might have used this document
        self.delete_pattern("query", "*")
        # Invalidate document-specific embeddings
        self.delete("embedding", f"doc:{document_id}")
        logger.info(f"Invalidated cache for document: {document_id}")

    def clear_all(self) -> bool:
        """
        Clear all RAG-related cache entries.

        Returns:
            True if successful, False otherwise.
        """
        if not self.is_available:
            return False

        try:
            deleted = 0
            for prefix in ["query", "embedding", "document"]:
                deleted += self.delete_pattern(prefix, "*")

            logger.info(f"Cleared all cache ({deleted} keys deleted)")
            return True

        except RedisError as e:
            logger.warning(f"Cache clear error: {e}")
            return False

    def get_statistics(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics.
        """
        if not self.is_available:
            return {
                "enabled": False,
                "connected": False,
            }

        try:
            info = self._client.info("stats")
            keyspace = self._client.info("keyspace")

            # Count RAG-specific keys
            rag_keys = len(list(self._client.scan_iter(match="rag:*", count=1000)))

            return {
                "enabled": True,
                "connected": True,
                "total_keys": keyspace.get("db0", {}).get("keys", 0),
                "rag_keys": rag_keys,
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(
                    info.get("keyspace_hits", 0),
                    info.get("keyspace_misses", 0),
                ),
            }

        except RedisError as e:
            logger.warning(f"Failed to get cache statistics: {e}")
            return {
                "enabled": True,
                "connected": False,
                "error": str(e),
            }

    def _get_default_ttl(self, prefix: str) -> int:
        """
        Get default TTL for a cache prefix.

        Args:
            prefix: Cache key prefix.

        Returns:
            TTL in seconds.
        """
        ttl_map = {
            "query": settings.cache_ttl_query,
            "embedding": settings.cache_ttl_embeddings,
            "document": settings.cache_ttl_documents,
        }
        return ttl_map.get(prefix, 3600)  # Default to 1 hour

    @staticmethod
    def _calculate_hit_rate(hits: int, misses: int) -> float:
        """Calculate cache hit rate."""
        total = hits + misses
        if total == 0:
            return 0.0
        return round((hits / total) * 100, 2)

    def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            self._client.close()
            logger.info("Redis connection closed")


# Singleton instance
_redis_cache: RedisCache | None = None


def get_redis_cache() -> RedisCache:
    """Get or create the Redis cache instance."""
    global _redis_cache
    if _redis_cache is None:
        _redis_cache = RedisCache()
    return _redis_cache


def reset_redis_cache() -> None:
    """Reset the Redis cache singleton (useful for testing)."""
    global _redis_cache
    if _redis_cache:
        _redis_cache.close()
    _redis_cache = None
