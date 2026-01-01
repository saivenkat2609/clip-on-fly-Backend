"""
HIGH PRIORITY FIX #24: Error Message Sanitization

This module provides utilities to sanitize error messages before returning them
to clients, preventing exposure of internal system details.

Security benefits:
- Prevents exposure of S3 bucket names
- Hides internal file paths and directory structure
- Obscures service names and API endpoints
- Removes stack traces and debug information
- Maintains useful error context for debugging in CloudWatch

Usage:
    from shared.error_sanitizer import sanitize_error_for_client, log_detailed_error

    try:
        # Some operation
        result = process_video(bucket='my-bucket', key='videos/secret.mp4')
    except Exception as e:
        # Log full error details to CloudWatch (for debugging)
        log_detailed_error(e, context={'bucket': 'my-bucket', 'key': 'videos/secret.mp4'})

        # Return sanitized error to client
        return {
            'statusCode': 500,
            'body': json.dumps({'error': sanitize_error_for_client(e)})
        }
"""

import re
import traceback
from typing import Dict, Any, Optional


# HIGH PRIORITY FIX #24: Patterns to remove from error messages
SENSITIVE_PATTERNS = [
    # S3 bucket names
    (r's3://[\w\-\.]+', 's3://[REDACTED]'),
    (r'bucket[:\s]+[\w\-\.]+', 'bucket: [REDACTED]'),
    (r'Bucket[=:\s]+[\w\-\.]+', 'Bucket=[REDACTED]'),

    # File paths (Unix and Windows)
    (r'/[\w\-/]+/(tmp|home|var|opt|usr)/[\w\-/\.]+', '/[REDACTED]/'),
    (r'C:\\[\w\-\\]+', 'C:\\[REDACTED]'),
    (r'/tmp/[\w\-/\.]+', '/tmp/[REDACTED]'),

    # AWS Account IDs
    (r'\d{12}', '[AWS_ACCOUNT_ID]'),

    # IP Addresses
    (r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '[IP_ADDRESS]'),

    # API Keys and tokens (partial - catches common patterns)
    (r'(?:api[_-]?key|token|secret)[=:\s]+[\w\-\.]+', '[API_KEY_REDACTED]'),

    # URLs with paths
    (r'https?://[\w\.\-]+/[\w\-/\.]+', 'https://[ENDPOINT]/[PATH]'),

    # ARNs
    (r'arn:aws:[\w\-:]+', 'arn:aws:[REDACTED]'),
]


# HIGH PRIORITY FIX #24: Mapping of specific errors to user-friendly messages
ERROR_MAPPINGS = {
    # S3 Errors
    'NoSuchKey': 'The requested file was not found',
    'NoSuchBucket': 'Storage location not found',
    'AccessDenied': 'Permission denied to access the resource',

    # DynamoDB Errors
    'ResourceNotFoundException': 'The requested resource was not found',
    'ProvisionedThroughputExceededException': 'Service temporarily unavailable due to high load',

    # Lambda Errors
    'TooManyRequestsException': 'Service temporarily unavailable. Please try again.',
    'ServiceException': 'An internal service error occurred',

    # Network Errors
    'ConnectionError': 'Unable to connect to the service',
    'TimeoutError': 'The request timed out',

    # YouTube/yt-dlp Errors
    'Video unavailable': 'The video is unavailable or private',
    'Sign in to confirm your age': 'This video requires age verification',
    'This video has been removed': 'The video has been removed from YouTube',
    'Private video': 'This video is private',

    # FFmpeg Errors
    'Invalid data found': 'Video file is corrupted or invalid',
    'Permission denied': 'Permission denied',
}


def sanitize_error_for_client(error: Exception, error_type: Optional[str] = None) -> str:
    """
    HIGH PRIORITY FIX #24: Sanitize error message for client response

    Removes sensitive information while maintaining useful context.

    Args:
        error: The exception object
        error_type: Optional error type for more specific messaging

    Returns:
        Sanitized error message safe to send to clients
    """
    error_str = str(error)

    # Check for known error types with friendly messages
    if error_type:
        if error_type in ERROR_MAPPINGS:
            return ERROR_MAPPINGS[error_type]

    # Check if error message contains known patterns
    for known_error, friendly_msg in ERROR_MAPPINGS.items():
        if known_error.lower() in error_str.lower():
            return friendly_msg

    # Apply regex patterns to remove sensitive data
    sanitized = error_str
    for pattern, replacement in SENSITIVE_PATTERNS:
        sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)

    # If message is too long or technical, use generic message
    if len(sanitized) > 200 or any(tech_term in sanitized.lower() for tech_term in [
        'traceback', 'exception', 'stacktrace', 'line ', 'file "', '__'
    ]):
        return 'An error occurred while processing your request. Please try again.'

    # Remove any remaining potential leaks
    sanitized = remove_technical_details(sanitized)

    return sanitized if sanitized else 'An error occurred. Please try again.'


def remove_technical_details(message: str) -> str:
    """
    Remove technical jargon and internal details from error message

    Args:
        message: Error message to clean

    Returns:
        Cleaned message
    """
    # Remove line numbers and file references
    message = re.sub(r'line \d+', '', message, flags=re.IGNORECASE)
    message = re.sub(r'File "[\w/\.\-]+"', '', message)

    # Remove Python exception details
    message = re.sub(r'Traceback \(most recent call last\):', '', message)
    message = re.sub(r'  File .+, line \d+', '', message)

    # Remove function/method references
    message = re.sub(r'in \w+\(\)', '', message)
    message = re.sub(r'at \w+\.\w+', '', message)

    # Clean up extra whitespace
    message = ' '.join(message.split())

    return message.strip()


def log_detailed_error(
    error: Exception,
    context: Optional[Dict[str, Any]] = None,
    prefix: str = '[ERROR]'
) -> None:
    """
    HIGH PRIORITY FIX #24: Log detailed error to CloudWatch for debugging

    This logs the FULL error details (including sensitive info) to CloudWatch
    for debugging purposes. Only the sanitized version goes to the client.

    Args:
        error: The exception object
        context: Additional context for debugging
        prefix: Log prefix for filtering
    """
    print(f"{prefix} Exception occurred: {type(error).__name__}")
    print(f"{prefix} Message: {str(error)}")

    if context:
        print(f"{prefix} Context: {context}")

    # Print full traceback to CloudWatch
    print(f"{prefix} Full traceback:")
    traceback.print_exc()


def create_error_response(
    error: Exception,
    status_code: int = 500,
    error_type: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    HIGH PRIORITY FIX #24: Create standardized error response

    Combines logging and sanitization into a single helper function.

    Args:
        error: The exception object
        status_code: HTTP status code (default 500)
        error_type: Optional error type for specific handling
        context: Additional context for CloudWatch logging

    Returns:
        Dict with statusCode, headers, and body suitable for Lambda return

    Example:
        try:
            result = risky_operation()
        except Exception as e:
            return create_error_response(
                e,
                status_code=500,
                error_type='VideoProcessingError',
                context={'session_id': session_id, 'user_id': user_id}
            )
    """
    # Log full details to CloudWatch
    log_detailed_error(error, context=context)

    # Return sanitized error to client
    import json
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'error': sanitize_error_for_client(error, error_type)
        })
    }


# HIGH PRIORITY FIX #24: Pre-defined error responses for common scenarios
class ErrorResponses:
    """Common error responses with appropriate status codes"""

    @staticmethod
    def video_not_found(session_id: str = None) -> Dict[str, Any]:
        """Video or session not found"""
        import json
        return {
            'statusCode': 404,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Video not found'})
        }

    @staticmethod
    def unauthorized() -> Dict[str, Any]:
        """Unauthorized access"""
        import json
        return {
            'statusCode': 401,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Unauthorized'})
        }

    @staticmethod
    def forbidden() -> Dict[str, Any]:
        """Forbidden - user doesn't own resource"""
        import json
        return {
            'statusCode': 403,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Forbidden - You can only access your own resources'})
        }

    @staticmethod
    def invalid_input(field: str = None) -> Dict[str, Any]:
        """Invalid input data"""
        import json
        message = f'Invalid {field}' if field else 'Invalid input'
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': message})
        }

    @staticmethod
    def rate_limit_exceeded() -> Dict[str, Any]:
        """Rate limit exceeded"""
        import json
        return {
            'statusCode': 429,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Rate limit exceeded. Please try again later.'})
        }

    @staticmethod
    def service_unavailable() -> Dict[str, Any]:
        """Service temporarily unavailable"""
        import json
        return {
            'statusCode': 503,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Service temporarily unavailable. Please try again.'})
        }
