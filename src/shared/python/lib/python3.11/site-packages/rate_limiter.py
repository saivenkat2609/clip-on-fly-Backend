"""
Rate Limiter Service
Implements per-user, per-endpoint rate limiting using DynamoDB
Uses sliding window algorithm to track request timestamps

Configuration:
- RATE_LIMIT_TABLE: DynamoDB table name (default: api_rate_limits)
- Rate limits defined in RATE_LIMITS dictionary below

DynamoDB Table Schema:
- Partition key: user_id (String)
- Sort key: endpoint (String)
- Attribute: timestamps (List of Numbers)
- Attribute: ttl (Number) - for automatic cleanup
"""

import boto3
import time
import os
from typing import Dict, Optional

# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ.get('RATE_LIMIT_TABLE', 'api_rate_limits'))

# Rate limit configuration (requests per time window in seconds)
RATE_LIMITS: Dict[str, Dict[str, int]] = {
    '/process': {'requests': 10, 'window': 3600},  # 10 YouTube processing requests per hour
    '/upload/generate-url': {'requests': 20, 'window': 3600},  # 20 upload URL generations per hour
    '/upload/start': {'requests': 10, 'window': 3600},  # 10 upload processing requests per hour
    '/status': {'requests': 100, 'window': 60},  # 100 status checks per minute
    '/result': {'requests': 100, 'window': 60},  # 100 result fetches per minute
}


def check_rate_limit(user_id: str, endpoint: str) -> bool:
    """
    Check if user has exceeded rate limit for the endpoint

    Args:
        user_id: User identifier from JWT
        endpoint: API endpoint path (e.g., '/process', '/upload/start')

    Returns:
        True if request is allowed, False if rate limit exceeded
    """
    # Get rate limit configuration for endpoint
    limit_config = RATE_LIMITS.get(endpoint)

    if not limit_config:
        # No rate limit configured for this endpoint - allow request
        print(f'[RateLimit] No limit configured for {endpoint} - allowing request')
        return True

    current_time = int(time.time())
    window_start = current_time - limit_config['window']

    try:
        # Get current request timestamps for user+endpoint
        response = table.get_item(
            Key={
                'user_id': user_id,
                'endpoint': endpoint
            }
        )

        if 'Item' in response:
            item = response['Item']

            # Filter timestamps to only those within the current window
            timestamps = [
                ts for ts in item.get('timestamps', [])
                if ts > window_start
            ]

            # Check if limit exceeded
            if len(timestamps) >= limit_config['requests']:
                print(f'[RateLimit] User {user_id} exceeded limit for {endpoint}: {len(timestamps)}/{limit_config["requests"]} requests in {limit_config["window"]}s')
                return False

            # Add current timestamp
            timestamps.append(current_time)

            # Update DynamoDB with new timestamp list
            table.put_item(Item={
                'user_id': user_id,
                'endpoint': endpoint,
                'timestamps': timestamps,
                'ttl': current_time + limit_config['window'] + 3600  # TTL: window + 1 hour buffer
            })

            print(f'[RateLimit] User {user_id} request allowed for {endpoint}: {len(timestamps)}/{limit_config["requests"]}')

        else:
            # First request for this user+endpoint
            table.put_item(Item={
                'user_id': user_id,
                'endpoint': endpoint,
                'timestamps': [current_time],
                'ttl': current_time + limit_config['window'] + 3600
            })

            print(f'[RateLimit] First request for user {user_id} on {endpoint}')

        return True

    except Exception as e:
        print(f'[RateLimit] Error checking rate limit: {str(e)}')
        # Fail open - allow request if rate limiting service fails
        # This prevents rate limiting issues from blocking all traffic
        return True


def get_rate_limit_info(user_id: str, endpoint: str) -> Optional[Dict]:
    """
    Get current rate limit status for user+endpoint

    Args:
        user_id: User identifier
        endpoint: API endpoint path

    Returns:
        Dictionary with rate limit info or None if no limit configured
    """
    limit_config = RATE_LIMITS.get(endpoint)

    if not limit_config:
        return None

    current_time = int(time.time())
    window_start = current_time - limit_config['window']

    try:
        response = table.get_item(
            Key={
                'user_id': user_id,
                'endpoint': endpoint
            }
        )

        if 'Item' in response:
            timestamps = [
                ts for ts in response['Item'].get('timestamps', [])
                if ts > window_start
            ]

            requests_remaining = limit_config['requests'] - len(timestamps)
            oldest_timestamp = min(timestamps) if timestamps else None
            reset_time = oldest_timestamp + limit_config['window'] if oldest_timestamp else None

            return {
                'limit': limit_config['requests'],
                'remaining': max(0, requests_remaining),
                'reset': reset_time,
                'window': limit_config['window']
            }
        else:
            return {
                'limit': limit_config['requests'],
                'remaining': limit_config['requests'],
                'reset': None,
                'window': limit_config['window']
            }

    except Exception as e:
        print(f'[RateLimit] Error getting rate limit info: {str(e)}')
        return None


def reset_rate_limit(user_id: str, endpoint: str) -> bool:
    """
    Reset rate limit for user+endpoint (admin function)

    Args:
        user_id: User identifier
        endpoint: API endpoint path

    Returns:
        True if reset successful, False otherwise
    """
    try:
        table.delete_item(
            Key={
                'user_id': user_id,
                'endpoint': endpoint
            }
        )
        print(f'[RateLimit] Reset rate limit for user {user_id} on {endpoint}')
        return True

    except Exception as e:
        print(f'[RateLimit] Error resetting rate limit: {str(e)}')
        return False
