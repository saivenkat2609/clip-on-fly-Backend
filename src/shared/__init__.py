"""
Shared utilities package for Lambda functions.

This package provides common utilities for:
- Circuit breakers (rate limiting, failure handling)
- Logging (structured JSON logs)
- Metrics (CloudWatch custom metrics)
- DynamoDB client (session management)
- WebSocket notifications (real-time updates)
- S3 utilities (prefix sharding, R2 support)
- Redis client (caching)
"""

__version__ = "1.0.0"

# Export commonly used items for convenience
__all__ = [
    'circuit_breaker',
    'logger',
    'metrics',
    'dynamodb_client',
    'websocket_notifier',
    's3_utils',
    'redis_client'
]
