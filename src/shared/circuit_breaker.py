"""
Circuit breaker pattern for external API calls.

Prevents cascading failures by failing fast when external services are unavailable.
Automatically detects when services recover and resumes normal operation.
"""

import time
from enum import Enum
from typing import Callable, Any, Optional
from functools import wraps


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = 1      # Normal operation - requests pass through
    OPEN = 2        # Failing - reject requests immediately
    HALF_OPEN = 3   # Testing - allow limited requests to test recovery


class CircuitBreakerOpen(Exception):
    """Exception raised when circuit breaker is open."""
    pass


class CircuitBreaker:
    """
    Circuit breaker for protecting against cascading failures.

    The circuit breaker starts in CLOSED state (normal operation).
    After N consecutive failures, it moves to OPEN state (reject immediately).
    After timeout, it moves to HALF_OPEN state (test recovery).
    After M consecutive successes in HALF_OPEN, it moves back to CLOSED.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: int = 60,
        success_threshold: int = 2,
        name: str = "default"
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            timeout: Seconds to wait before trying again (OPEN → HALF_OPEN)
            success_threshold: Consecutive successes needed to close circuit
            name: Name for logging/identification
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.success_threshold = success_threshold
        self.name = name

        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Function to call
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Result from function call

        Raises:
            CircuitBreakerOpen: If circuit is open
            Exception: If function raises an exception
        """
        # If circuit is OPEN, check if timeout has passed
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.timeout:
                print(f"Circuit breaker [{self.name}]: OPEN → HALF_OPEN (testing recovery)")
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
            else:
                time_remaining = int(self.timeout - (time.time() - self.last_failure_time))
                raise CircuitBreakerOpen(
                    f"Circuit breaker [{self.name}] is OPEN. "
                    f"Service unavailable. Retry in {time_remaining}s"
                )

        try:
            # Call the function
            result = func(*args, **kwargs)

            # Success
            self.on_success()
            return result

        except Exception as e:
            # Failure
            self.on_failure()
            raise e

    def on_success(self):
        """Handle successful call."""
        self.failure_count = 0

        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                print(f"Circuit breaker [{self.name}]: HALF_OPEN → CLOSED (recovered)")
                self.state = CircuitState.CLOSED
                self.success_count = 0

    def on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        self.success_count = 0

        if self.failure_count >= self.failure_threshold:
            if self.state != CircuitState.OPEN:
                print(
                    f"Circuit breaker [{self.name}]: {self.state.name} → OPEN "
                    f"({self.failure_count} consecutive failures)"
                )
                self.state = CircuitState.OPEN

    def reset(self):
        """Reset circuit breaker to initial state (admin function)."""
        print(f"Circuit breaker [{self.name}]: Manual reset to CLOSED")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None

    def get_status(self) -> dict:
        """
        Get current circuit breaker status.

        Returns:
            Dictionary with status information
        """
        status = {
            'name': self.name,
            'state': self.state.name,
            'failure_count': self.failure_count,
            'success_count': self.success_count,
            'failure_threshold': self.failure_threshold,
            'success_threshold': self.success_threshold,
            'timeout': self.timeout
        }

        if self.state == CircuitState.OPEN and self.last_failure_time:
            time_remaining = int(self.timeout - (time.time() - self.last_failure_time))
            status['retry_after'] = max(0, time_remaining)

        return status


# Global circuit breakers for common external services
# These are reused across Lambda invocations (warm start optimization)
groq_circuit_breaker = CircuitBreaker(
    failure_threshold=3,
    timeout=30,
    success_threshold=2,
    name="groq_api"
)

assemblyai_circuit_breaker = CircuitBreaker(
    failure_threshold=3,
    timeout=30,
    success_threshold=2,
    name="assemblyai_api"
)

deepgram_circuit_breaker = CircuitBreaker(
    failure_threshold=3,
    timeout=30,
    success_threshold=2,
    name="deepgram_api"
)

youtube_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    timeout=60,
    success_threshold=2,
    name="youtube"
)


def circuit_breaker_decorator(
    breaker: Optional[CircuitBreaker] = None,
    failure_threshold: int = 5,
    timeout: int = 60,
    success_threshold: int = 2,
    name: str = "default"
):
    """
    Decorator to apply circuit breaker to a function.

    Args:
        breaker: Existing CircuitBreaker instance (optional)
        failure_threshold: Number of failures before opening
        timeout: Seconds before testing recovery
        success_threshold: Consecutive successes to close
        name: Circuit breaker name

    Usage:
        @circuit_breaker_decorator(name="my_api")
        def call_external_api():
            # ... API call ...

        # Or with existing breaker:
        @circuit_breaker_decorator(breaker=groq_circuit_breaker)
        def call_groq():
            # ... Groq API call ...
    """
    # Create breaker if not provided
    if breaker is None:
        breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            timeout=timeout,
            success_threshold=success_threshold,
            name=name
        )

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            return breaker.call(func, *args, **kwargs)
        return wrapper

    return decorator


def with_fallback(
    primary_func: Callable,
    fallback_func: Callable,
    breaker: Optional[CircuitBreaker] = None,
    **breaker_kwargs
) -> Any:
    """
    Execute primary function with automatic fallback if circuit is open.

    Args:
        primary_func: Primary function to try
        fallback_func: Fallback function if primary fails or circuit is open
        breaker: CircuitBreaker instance (optional)
        **breaker_kwargs: Arguments for creating new CircuitBreaker

    Returns:
        Result from primary_func or fallback_func

    Usage:
        result = with_fallback(
            primary_func=lambda: call_groq_api(),
            fallback_func=lambda: call_assemblyai_api(),
            breaker=groq_circuit_breaker
        )
    """
    if breaker is None:
        breaker = CircuitBreaker(**breaker_kwargs)

    try:
        return breaker.call(primary_func)
    except CircuitBreakerOpen as e:
        print(f"Circuit breaker open, using fallback: {str(e)}")
        return fallback_func()
    except Exception as e:
        print(f"Primary function failed, using fallback: {str(e)}")
        return fallback_func()


# Export commonly used items
__all__ = [
    'CircuitBreaker',
    'CircuitState',
    'CircuitBreakerOpen',
    'circuit_breaker_decorator',
    'with_fallback',
    'groq_circuit_breaker',
    'assemblyai_circuit_breaker',
    'deepgram_circuit_breaker',
    'youtube_circuit_breaker'
]
