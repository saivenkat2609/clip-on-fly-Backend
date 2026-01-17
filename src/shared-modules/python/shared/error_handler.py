"""
Centralized Error Handler for Lambda Functions

Provides standardized error categorization, user-friendly messages,
and structured error responses for consistent error handling across all Lambdas.
"""

from enum import Enum
from typing import Dict, Any, Optional
import json


class ErrorCategory(Enum):
    """Error categories for classification and handling"""
    VALIDATION_ERROR = "validation_error"      # User input issues (bad URL, invalid format)
    RESOURCE_ERROR = "resource_error"          # Video not found, unavailable, deleted
    PROCESSING_ERROR = "processing_error"      # FFmpeg, transcription failures
    RATE_LIMIT_ERROR = "rate_limit_error"      # API rate limits exceeded
    NETWORK_ERROR = "network_error"            # Transient network issues, timeouts
    INTERNAL_ERROR = "internal_error"          # Unexpected errors, bugs


class ErrorResponse:
    """
    Structured error response for Lambda functions

    Separates technical error details (for logs) from user-friendly messages
    """

    def __init__(
        self,
        category: ErrorCategory,
        message: str,
        user_message: str,
        retry_after: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize error response

        Args:
            category: Error category enum
            message: Technical message for logs
            user_message: User-friendly message to display
            retry_after: Seconds until user can retry (for rate limits)
            details: Additional context (session_id, etc.)
        """
        self.category = category
        self.message = message  # Technical message (logs)
        self.user_message = user_message  # User-friendly message
        self.retry_after = retry_after
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        result = {
            'category': self.category.value,
            'message': self.user_message,
            'can_retry': self.category in [
                ErrorCategory.NETWORK_ERROR,
                ErrorCategory.RATE_LIMIT_ERROR
            ]
        }

        if self.retry_after is not None:
            result['retry_after'] = self.retry_after

        return result

    def to_json(self) -> str:
        """Convert to JSON string for Lambda response"""
        return json.dumps(self.to_dict())


class ValidationError(Exception):
    """Validation error for user input"""
    pass


class ResourceError(Exception):
    """Resource not found or unavailable"""
    pass


class ProcessingError(Exception):
    """Processing failure (FFmpeg, etc.)"""
    pass


class RateLimitException(Exception):
    """Rate limit exceeded"""
    pass


def handle_lambda_error(error: Exception, session_id: str, context: Optional[Dict] = None) -> ErrorResponse:
    """
    Categorize and handle Lambda errors

    Args:
        error: Exception raised
        session_id: Video session identifier
        context: Additional context information

    Returns:
        ErrorResponse with categorized error information
    """
    context = context or {}

    # Validation errors (user input issues)
    if isinstance(error, ValidationError):
        return ErrorResponse(
            ErrorCategory.VALIDATION_ERROR,
            str(error),
            "Invalid video format or settings. Please check your input and try again.",
            details={'session_id': session_id, **context}
        )

    # Resource errors (video not found, unavailable)
    elif isinstance(error, ResourceError):
        return ErrorResponse(
            ErrorCategory.RESOURCE_ERROR,
            str(error),
            "Unable to access the video. It may be private, deleted, or unavailable in your region.",
            details={'session_id': session_id, **context}
        )

    # Processing errors (FFmpeg, transcription failures)
    elif isinstance(error, ProcessingError):
        return ErrorResponse(
            ErrorCategory.PROCESSING_ERROR,
            str(error),
            "Video processing failed. Please try again or contact support if the issue persists.",
            details={'session_id': session_id, **context}
        )

    # Rate limit errors
    elif isinstance(error, RateLimitException):
        return ErrorResponse(
            ErrorCategory.RATE_LIMIT_ERROR,
            str(error),
            "Too many requests. Please try again in a few minutes.",
            retry_after=300,  # 5 minutes
            details={'session_id': session_id, **context}
        )

    # Network/timeout errors
    elif 'timeout' in str(error).lower() or 'network' in str(error).lower():
        return ErrorResponse(
            ErrorCategory.NETWORK_ERROR,
            str(error),
            "Network timeout. Please check your connection and try again.",
            retry_after=30,  # 30 seconds
            details={'session_id': session_id, **context}
        )

    # Default: Internal error
    else:
        return ErrorResponse(
            ErrorCategory.INTERNAL_ERROR,
            str(error),
            "An unexpected error occurred. Our team has been notified and is working on a fix.",
            details={'session_id': session_id, **context}
        )


def sanitize_error_message(error_msg: str) -> str:
    """
    Sanitize error messages to remove sensitive information

    Removes:
    - File paths (/tmp/, /opt/, etc.)
    - AWS ARNs
    - Session IDs in URLs
    - API keys or tokens

    Args:
        error_msg: Raw error message

    Returns:
        Sanitized error message
    """
    import re

    # Remove file paths
    error_msg = re.sub(r'/[a-zA-Z0-9_/.-]+', '[path removed]', error_msg)

    # Remove AWS ARNs
    error_msg = re.sub(r'arn:aws:[a-z0-9-]+:[a-z0-9-]*:\d+:[a-z0-9-/_]+', '[ARN removed]', error_msg)

    # Remove UUIDs/session IDs
    error_msg = re.sub(
        r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
        '[ID removed]',
        error_msg,
        flags=re.IGNORECASE
    )

    # Remove potential API keys (long alphanumeric strings)
    error_msg = re.sub(r'[A-Za-z0-9]{32,}', '[key removed]', error_msg)

    return error_msg


# Export commonly used items
__all__ = [
    'ErrorCategory',
    'ErrorResponse',
    'ValidationError',
    'ResourceError',
    'ProcessingError',
    'RateLimitException',
    'handle_lambda_error',
    'sanitize_error_message'
]
