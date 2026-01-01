"""
Security Logger Service
Logs security-relevant events for monitoring and auditing

Features:
- API request logging with user identification
- Rate limit violation tracking
- Authentication failure logging
- Suspicious activity detection
- Structured JSON logging for CloudWatch

All logs are printed to stdout and automatically sent to CloudWatch Logs
by Lambda. Use CloudWatch Insights to query and analyze logs.

Example CloudWatch Insights queries:
1. Find all rate limit violations:
   fields @timestamp, user_id, endpoint
   | filter event_type = "RATE_LIMIT_EXCEEDED"
   | sort @timestamp desc

2. Find failed authentications:
   fields @timestamp, reason, ip_address
   | filter event_type = "AUTH_FAILED"
   | stats count() by reason
"""

import json
import time
from typing import Dict, Optional, Any


def log_api_request(user_id: str, endpoint: str, event: Dict) -> None:
    """
    Log an API request for security monitoring

    Args:
        user_id: Verified user ID from JWT
        endpoint: API endpoint path
        event: Lambda event object
    """
    request_context = event.get('requestContext', {})
    identity = request_context.get('identity', {})

    log_entry = {
        'event_type': 'API_REQUEST',
        'timestamp': int(time.time() * 1000),
        'user_id': user_id,
        'endpoint': endpoint,
        'method': event.get('httpMethod'),
        'ip_address': identity.get('sourceIp', 'unknown'),
        'user_agent': event.get('headers', {}).get('User-Agent', 'unknown'),
        'request_id': request_context.get('requestId'),
        'api_id': request_context.get('apiId'),
    }

    print(f'[SECURITY] {json.dumps(log_entry)}')


def log_rate_limit_violation(user_id: str, endpoint: str, current_count: Optional[int] = None, limit: Optional[int] = None) -> None:
    """
    Log a rate limit violation

    Args:
        user_id: User who exceeded the rate limit
        endpoint: API endpoint
        current_count: Current number of requests (optional)
        limit: Rate limit threshold (optional)
    """
    log_entry = {
        'event_type': 'RATE_LIMIT_EXCEEDED',
        'severity': 'HIGH',
        'timestamp': int(time.time() * 1000),
        'user_id': user_id,
        'endpoint': endpoint,
        'current_count': current_count,
        'limit': limit,
        'message': f'User {user_id} exceeded rate limit for {endpoint}'
    }

    print(f'[SECURITY] {json.dumps(log_entry)}')


def log_auth_failure(reason: str, token_prefix: str = '', ip_address: str = 'unknown', additional_info: Optional[Dict] = None) -> None:
    """
    Log an authentication failure

    Args:
        reason: Reason for authentication failure
        token_prefix: First few characters of token for debugging (optional)
        ip_address: Source IP address (optional)
        additional_info: Additional context (optional)
    """
    log_entry = {
        'event_type': 'AUTH_FAILED',
        'severity': 'HIGH',
        'timestamp': int(time.time() * 1000),
        'reason': reason,
        'token_prefix': token_prefix[:10] if token_prefix else '',  # Only log first 10 chars
        'ip_address': ip_address,
        'additional_info': additional_info or {}
    }

    print(f'[SECURITY] {json.dumps(log_entry)}')


def log_suspicious_activity(user_id: str, activity_type: str, details: Dict) -> None:
    """
    Log suspicious activity for investigation

    Args:
        user_id: User associated with suspicious activity
        activity_type: Type of suspicious activity
        details: Additional details about the activity
    """
    log_entry = {
        'event_type': 'SUSPICIOUS_ACTIVITY',
        'severity': 'CRITICAL',
        'timestamp': int(time.time() * 1000),
        'user_id': user_id,
        'activity_type': activity_type,
        'details': details
    }

    print(f'[SECURITY] {json.dumps(log_entry)}')


def log_access_denied(user_id: str, resource: str, reason: str, ip_address: str = 'unknown') -> None:
    """
    Log an access denied event (authorization failure)

    Args:
        user_id: User who was denied access
        resource: Resource that was accessed
        reason: Reason for denial
        ip_address: Source IP address
    """
    log_entry = {
        'event_type': 'ACCESS_DENIED',
        'severity': 'MEDIUM',
        'timestamp': int(time.time() * 1000),
        'user_id': user_id,
        'resource': resource,
        'reason': reason,
        'ip_address': ip_address
    }

    print(f'[SECURITY] {json.dumps(log_entry)}')


def log_security_event(event_type: str, severity: str, user_id: str, details: Dict[str, Any]) -> None:
    """
    Generic security event logger

    Args:
        event_type: Type of security event
        severity: Event severity (LOW, MEDIUM, HIGH, CRITICAL)
        user_id: User associated with the event
        details: Event details
    """
    log_entry = {
        'event_type': event_type,
        'severity': severity,
        'timestamp': int(time.time() * 1000),
        'user_id': user_id,
        'details': details
    }

    print(f'[SECURITY] {json.dumps(log_entry)}')


def log_token_refresh(user_id: str, old_token_expires: Optional[int] = None, new_token_expires: Optional[int] = None) -> None:
    """
    Log a token refresh event

    Args:
        user_id: User whose token was refreshed
        old_token_expires: Old token expiration timestamp
        new_token_expires: New token expiration timestamp
    """
    log_entry = {
        'event_type': 'TOKEN_REFRESH',
        'severity': 'LOW',
        'timestamp': int(time.time() * 1000),
        'user_id': user_id,
        'old_token_expires': old_token_expires,
        'new_token_expires': new_token_expires
    }

    print(f'[SECURITY] {json.dumps(log_entry)}')


def log_data_access(user_id: str, resource_type: str, resource_id: str, action: str) -> None:
    """
    Log data access for audit trails

    Args:
        user_id: User who accessed the data
        resource_type: Type of resource (e.g., 'video', 'project')
        resource_id: Resource identifier
        action: Action performed (e.g., 'read', 'update', 'delete')
    """
    log_entry = {
        'event_type': 'DATA_ACCESS',
        'severity': 'LOW',
        'timestamp': int(time.time() * 1000),
        'user_id': user_id,
        'resource_type': resource_type,
        'resource_id': resource_id,
        'action': action
    }

    print(f'[SECURITY] {json.dumps(log_entry)}')


# Helper function to extract IP from event
def get_client_ip(event: Dict) -> str:
    """
    Extract client IP address from Lambda event

    Args:
        event: Lambda event object

    Returns:
        Client IP address or 'unknown'
    """
    request_context = event.get('requestContext', {})
    identity = request_context.get('identity', {})
    return identity.get('sourceIp', 'unknown')


# Helper function to detect potential attacks
def detect_suspicious_patterns(event: Dict) -> Optional[str]:
    """
    Detect common attack patterns in requests

    Args:
        event: Lambda event object

    Returns:
        Description of suspicious pattern if detected, None otherwise
    """
    body = event.get('body', '')
    headers = event.get('headers', {})

    # Check for SQL injection patterns
    if any(pattern in body.lower() for pattern in ['union select', 'drop table', '1=1', '-- ']):
        return 'Potential SQL injection attempt'

    # Check for XSS patterns
    if any(pattern in body.lower() for pattern in ['<script', 'javascript:', 'onerror=']):
        return 'Potential XSS attempt'

    # Check for path traversal
    if '../' in body or '..\\' in body:
        return 'Potential path traversal attempt'

    # Check for abnormally large requests
    if len(body) > 1024 * 1024:  # 1MB
        return 'Abnormally large request body'

    # Check for suspicious user agents
    suspicious_agents = ['sqlmap', 'nikto', 'nmap', 'masscan', 'burp']
    user_agent = headers.get('User-Agent', '').lower()
    if any(agent in user_agent for agent in suspicious_agents):
        return f'Suspicious user agent: {user_agent}'

    return None
