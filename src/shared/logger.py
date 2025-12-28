"""
Structured logging module for Lambda functions.

Provides JSON-formatted logs for easy parsing and querying in CloudWatch Logs Insights.
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional


class StructuredLogger:
    """
    Logger that outputs structured JSON logs.

    Benefits:
    - Easy to query in CloudWatch Logs Insights
    - Includes context (user_id, session_id, etc.)
    - Consistent format across all Lambda functions
    """

    def __init__(self, service_name: str, log_level: str = 'INFO'):
        """
        Initialize structured logger.

        Args:
            service_name: Name of the service/Lambda function
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        """
        self.service_name = service_name
        self.logger = logging.getLogger(service_name)

        # Set log level
        level = getattr(logging, log_level.upper(), logging.INFO)
        self.logger.setLevel(level)

        # Remove existing handlers
        self.logger.handlers = []

        # Add console handler
        handler = logging.StreamHandler()
        handler.setLevel(level)
        self.logger.addHandler(handler)

        # Context that persists across log calls
        self.context = {}

    def set_context(self, **kwargs):
        """
        Set persistent context for all log messages.

        Usage:
            logger.set_context(user_id='user123', session_id='sess456')
            logger.info('Processing video')  # Will include user_id and session_id
        """
        self.context.update(kwargs)

    def clear_context(self):
        """Clear persistent context."""
        self.context = {}

    def _log(self, level: str, message: str, **kwargs):
        """Internal log method that formats and outputs JSON."""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': level,
            'service': self.service_name,
            'message': message,
            **self.context,  # Include persistent context
            **kwargs  # Include call-specific context
        }

        # Remove None values
        log_entry = {k: v for k, v in log_entry.items() if v is not None}

        # Print JSON (will appear in CloudWatch Logs)
        print(json.dumps(log_entry))

    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self._log('DEBUG', message, **kwargs)

    def info(self, message: str, **kwargs):
        """Log info message."""
        self._log('INFO', message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self._log('WARNING', message, **kwargs)

    def error(self, message: str, error: Optional[Exception] = None, **kwargs):
        """
        Log error message.

        Args:
            message: Error message
            error: Exception object (optional)
            **kwargs: Additional context
        """
        error_context = {}
        if error:
            error_context = {
                'error_type': type(error).__name__,
                'error_message': str(error)
            }

        self._log('ERROR', message, **error_context, **kwargs)

    def exception(self, message: str, **kwargs):
        """Log exception with stack trace."""
        import traceback
        self._log(
            'ERROR',
            message,
            stack_trace=traceback.format_exc(),
            **kwargs
        )


# Lambda-specific logger factory
def get_lambda_logger(context=None) -> StructuredLogger:
    """
    Create logger for Lambda function with automatic context extraction.

    Args:
        context: Lambda context object

    Returns:
        StructuredLogger instance

    Usage:
        def lambda_handler(event, context):
            logger = get_lambda_logger(context)
            logger.info('Processing request', user_id=event['user_id'])
    """
    # Get function name from context or environment
    if context:
        function_name = context.function_name
        request_id = context.aws_request_id
    else:
        function_name = os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'unknown')
        request_id = None

    logger = StructuredLogger(function_name)

    # Set Lambda context
    if request_id:
        logger.set_context(request_id=request_id)

    return logger


# Performance logging decorator
def log_execution_time(logger: StructuredLogger):
    """
    Decorator to log function execution time.

    Usage:
        @log_execution_time(logger)
        def process_video(session_id):
            # ... process video ...
    """
    import time
    from functools import wraps

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            func_name = func.__name__

            logger.debug(f'Starting {func_name}')

            try:
                result = func(*args, **kwargs)
                duration_ms = int((time.time() - start_time) * 1000)

                logger.info(
                    f'Completed {func_name}',
                    function=func_name,
                    duration_ms=duration_ms,
                    status='success'
                )

                return result

            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)

                logger.error(
                    f'Failed {func_name}',
                    error=e,
                    function=func_name,
                    duration_ms=duration_ms,
                    status='failure'
                )

                raise

        return wrapper
    return decorator


# CloudWatch Logs Insights query helpers
COMMON_QUERIES = {
    'errors': """
        fields @timestamp, level, message, error_type, error_message
        | filter level = "ERROR"
        | sort @timestamp desc
        | limit 100
    """,

    'slow_requests': """
        fields @timestamp, service, message, duration_ms
        | filter duration_ms > 3000
        | sort duration_ms desc
        | limit 50
    """,

    'by_user': """
        fields @timestamp, message, user_id, session_id
        | filter user_id = "{user_id}"
        | sort @timestamp desc
    """,

    'processing_pipeline': """
        fields @timestamp, service, message, session_id, duration_ms
        | filter session_id = "{session_id}"
        | sort @timestamp asc
    """
}


def get_query_template(query_name: str, **params) -> str:
    """
    Get CloudWatch Logs Insights query template.

    Args:
        query_name: Name of query (errors, slow_requests, by_user, processing_pipeline)
        **params: Parameters to substitute in query (e.g., user_id, session_id)

    Returns:
        Query string with parameters substituted

    Usage:
        query = get_query_template('by_user', user_id='user123')
    """
    query = COMMON_QUERIES.get(query_name, "")
    return query.format(**params)


# Simple factory function (alias for convenience)
def get_logger(service_name: str, log_level: str = 'INFO') -> StructuredLogger:
    """
    Simple factory to create a StructuredLogger instance.

    Args:
        service_name: Name of the service/Lambda function
        log_level: Logging level (default: INFO)

    Returns:
        StructuredLogger instance

    Usage:
        logger = get_logger('detect-clips')
        logger.info('Processing video', session_id='abc123')
    """
    return StructuredLogger(service_name, log_level)


# Export commonly used items
__all__ = [
    'StructuredLogger',
    'get_lambda_logger',
    'get_logger',
    'log_execution_time',
    'get_query_template',
    'COMMON_QUERIES'
]
