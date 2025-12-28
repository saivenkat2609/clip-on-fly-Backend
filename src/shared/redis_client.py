"""
Redis client for caching and rate limiting.

This module provides a singleton Redis client for use across Lambda functions.
Requires Lambda to be deployed in a VPC with access to ElastiCache Redis.
"""

import redis
import os
import json
import time
from typing import Any, Optional
from functools import wraps


class RedisClient:
    """Singleton Redis client with connection pooling."""

    _instance = None
    _client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RedisClient, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize Redis client (only once)."""
        if self._client is None:
            redis_endpoint = os.environ.get('REDIS_ENDPOINT', 'localhost')
            redis_port = int(os.environ.get('REDIS_PORT', 6379))
            redis_password = os.environ.get('REDIS_PASSWORD', None)

            self._client = redis.Redis(
                host=redis_endpoint,
                port=redis_port,
                password=redis_password,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
                socket_keepalive=True,
                connection_pool=redis.ConnectionPool(
                    host=redis_endpoint,
                    port=redis_port,
                    password=redis_password,
                    max_connections=10,
                    decode_responses=True
                )
            )
            print(f"Redis client initialized: {redis_endpoint}:{redis_port}")

    @property
    def client(self):
        """Get Redis client instance."""
        return self._client

    def get(self, key: str) -> Optional[str]:
        """Get value from cache."""
        try:
            return self._client.get(key)
        except Exception:
            # Silently fail if Redis unavailable (saves logs when not using Redis)
            return None

    def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """Set value in cache with optional TTL."""
        try:
            if ttl:
                return self._client.setex(key, ttl, value)
            else:
                return self._client.set(key, value)
        except Exception:
            # Silently fail if Redis unavailable
            return False

    def get_json(self, key: str) -> Optional[Any]:
        """Get JSON value from cache."""
        try:
            value = self._client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception:
            # Silently fail if Redis unavailable
            return None

    def set_json(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set JSON value in cache with optional TTL."""
        try:
            json_str = json.dumps(value)
            if ttl:
                return self._client.setex(key, ttl, json_str)
            else:
                return self._client.set(key, json_str)
        except Exception:
            # Silently fail if Redis unavailable
            return False

    def delete(self, *keys: str) -> int:
        """Delete one or more keys."""
        try:
            return self._client.delete(*keys)
        except Exception:
            # Silently fail if Redis unavailable
            return 0

    def exists(self, key: str) -> bool:
        """Check if key exists."""
        try:
            return self._client.exists(key) > 0
        except Exception as e:
            print(f"Redis EXISTS error for key '{key}': {str(e)}")
            return False

    def ttl(self, key: str) -> int:
        """Get TTL for key in seconds."""
        try:
            return self._client.ttl(key)
        except Exception as e:
            print(f"Redis TTL error for key '{key}': {str(e)}")
            return -1

    def incr(self, key: str) -> Optional[int]:
        """Increment counter."""
        try:
            return self._client.incr(key)
        except Exception as e:
            print(f"Redis INCR error for key '{key}': {str(e)}")
            return None

    def expire(self, key: str, ttl: int) -> bool:
        """Set expiration for key."""
        try:
            return self._client.expire(key, ttl)
        except Exception as e:
            print(f"Redis EXPIRE error for key '{key}': {str(e)}")
            return False

    def invalidate_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern."""
        try:
            keys = self._client.keys(pattern)
            if keys:
                return self._client.delete(*keys)
            return 0
        except Exception as e:
            print(f"Redis invalidate pattern error for '{pattern}': {str(e)}")
            return 0


# Singleton instance
redis_client = RedisClient()


# Cache decorator
def redis_cache(ttl: int = 300, key_prefix: str = "cache"):
    """
    Decorator to cache function results in Redis.

    Args:
        ttl: Time to live in seconds (default: 5 minutes)
        key_prefix: Prefix for cache key

    Usage:
        @redis_cache(ttl=600, key_prefix="user_videos")
        def get_user_videos(user_id):
            # ... expensive operation ...
            return videos
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{key_prefix}:{func.__name__}:{str(args)}:{str(kwargs)}"

            # Try to get from cache
            cached_value = redis_client.get_json(cache_key)
            if cached_value is not None:
                print(f"Cache HIT: {cache_key}")
                return cached_value

            # Cache miss - call function
            print(f"Cache MISS: {cache_key}")
            result = func(*args, **kwargs)

            # Store in cache
            redis_client.set_json(cache_key, result, ttl)

            return result
        return wrapper
    return decorator


# Helper functions for common cache operations
def cache_session_status(session_id: str, status_data: dict, ttl: int = 30):
    """Cache session status with 30-second TTL."""
    key = f"status:{session_id}"
    return redis_client.set_json(key, status_data, ttl)


def get_cached_session_status(session_id: str) -> Optional[dict]:
    """Get cached session status."""
    key = f"status:{session_id}"
    return redis_client.get_json(key)


def cache_session_result(session_id: str, result_data: dict, ttl: int = 3600):
    """Cache session result with 1-hour TTL."""
    key = f"result:{session_id}"
    return redis_client.set_json(key, result_data, ttl)


def get_cached_session_result(session_id: str) -> Optional[dict]:
    """Get cached session result."""
    key = f"result:{session_id}"
    return redis_client.get_json(key)


def invalidate_session_cache(session_id: str):
    """Invalidate all cache for a session."""
    return redis_client.delete(
        f"status:{session_id}",
        f"result:{session_id}"
    )


# Export commonly used items
__all__ = [
    'redis_client',
    'RedisClient',
    'redis_cache',
    'cache_session_status',
    'get_cached_session_status',
    'cache_session_result',
    'get_cached_session_result',
    'invalidate_session_cache'
]
