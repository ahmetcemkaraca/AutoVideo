#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Error handling and categorization for VideoAutomation pipeline.

Provides structured error types, retry policies, and error recovery mechanisms.
"""

import time
import enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime, timedelta
from functools import wraps
import logging

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Error Categories
# ═══════════════════════════════════════════════════════════════════════════════

class ErrorCategory(enum.Enum):
    """Categories of errors for handling and reporting."""
    TRANSIENT = "transient"           # Temporary failures (network, rate limits)
    RETRYABLE = "retryable"           # Can be retried with backoff
    PERMANENT = "permanent"           # Fatal errors, won't recover
    CONFIGURATION = "configuration"   # Invalid config or setup
    AUTHENTICATION = "authentication" # Auth failures
    QUOTA = "quota"                   # API quota exceeded
    VALIDATION = "validation"         # Input validation failures


class ErrorSeverity(enum.Enum):
    """Severity levels for error handling."""
    LOW = "low"           # Non-critical, can continue
    MEDIUM = "medium"     # Warning, may affect functionality
    HIGH = "high"         # Critical, operation failed
    CRITICAL = "critical" # System-level failure


@dataclass
class ErrorContext:
    """Context information for an error."""
    timestamp: datetime = field(default_factory=datetime.now)
    category: ErrorCategory = ErrorCategory.TRANSIENT
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    can_retry: bool = True
    suggested_action: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# Custom Exceptions
# ═══════════════════════════════════════════════════════════════════════════════

class PipelineError(Exception):
    """Base exception for pipeline errors."""

    def __init__(self, message: str, context: Optional[ErrorContext] = None):
        super().__init__(message)
        self.context = context or ErrorContext(message=message)


class YouTubeUploadError(PipelineError):
    """YouTube upload specific errors."""
    pass


class VideoRenderError(PipelineError):
    """Video rendering errors."""
    pass


class AudioProcessingError(PipelineError):
    """Audio processing errors."""
    pass


class ConfigValidationError(PipelineError):
    """Configuration validation errors."""
    pass


class StateCorruptionError(PipelineError):
    """State file corruption errors."""
    pass


class AuthenticationError(PipelineError):
    """Authentication errors."""
    pass


class QuotaExceededError(PipelineError):
    """API quota exceeded errors."""
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# Error Categorization
# ═══════════════════════════════════════════════════════════════════════════════

def categorize_google_api_error(status_code: int, error_message: str) -> ErrorContext:
    """
    Categorize Google API errors based on status code and message.

    Args:
        status_code: HTTP status code
        error_message: Error message from API

    Returns:
        ErrorContext with appropriate categorization
    """
    context = ErrorContext(
        message=f"API error {status_code}: {error_message}",
        details={"status_code": status_code}
    )

    # Rate limiting / quota errors
    if status_code == 429:
        context.category = ErrorCategory.QUOTA
        context.severity = ErrorSeverity.HIGH
        context.can_retry = True
        context.suggested_action = "Wait and retry with exponential backoff"

    # Server errors (transient)
    elif status_code in [500, 502, 503, 504]:
        context.category = ErrorCategory.TRANSIENT
        context.severity = ErrorSeverity.MEDIUM
        context.can_retry = True
        context.suggested_action = f"Retry with exponential backoff (max 10 attempts)"

    # Authentication errors
    elif status_code == 401:
        context.category = ErrorCategory.AUTHENTICATION
        context.severity = ErrorSeverity.CRITICAL
        context.can_retry = False
        context.suggested_action = "Re-authenticate with YouTube API"

    # Authorization / permission errors
    elif status_code == 403:
        if "quota" in error_message.lower():
            context.category = ErrorCategory.QUOTA
            context.severity = ErrorSeverity.HIGH
            context.can_retry = False
            context.suggested_action = "Wait for quota reset or increase quota"
        else:
            context.category = ErrorCategory.AUTHENTICATION
            context.severity = ErrorSeverity.CRITICAL
            context.can_retry = False
            context.suggested_action = "Check API permissions and scopes"

    # Not found
    elif status_code == 404:
        context.category = ErrorCategory.PERMANENT
        context.severity = ErrorSeverity.HIGH
        context.can_retry = False
        context.suggested_action = "Verify resource exists and is accessible"

    # Bad request
    elif status_code == 400:
        context.category = ErrorCategory.VALIDATION
        context.severity = ErrorSeverity.HIGH
        context.can_retry = False
        context.suggested_action = "Fix request parameters and retry"

    # Default to retryable
    else:
        context.category = ErrorCategory.RETRYABLE
        context.severity = ErrorSeverity.MEDIUM
        context.can_retry = True

    return context


# ═══════════════════════════════════════════════════════════════════════════════
# Retry Policy
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class RetryPolicy:
    """Configuration for retry behavior."""
    max_attempts: int = 10
    base_delay: float = 1.0  # Base delay in seconds
    max_delay: float = 600.0  # Maximum delay (10 minutes)
    exponential_base: float = 2.0  # Exponential backoff base
    jitter: bool = True  # Add random jitter to prevent thundering herd

    def get_delay(self, attempt: int) -> float:
        """
        Calculate delay for a given retry attempt using exponential backoff.

        Args:
            attempt: Retry attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        import random

        delay = min(
            self.base_delay * (self.exponential_base ** attempt),
            self.max_delay
        )

        if self.jitter:
            # Add +/- 25% random jitter
            jitter_range = delay * 0.25
            delay += random.uniform(-jitter_range, jitter_range)

        return max(0, delay)


# ═══════════════════════════════════════════════════════════════════════════════
# Error Tracking
# ═══════════════════════════════════════════════════════════════════════════════

class ErrorTracker:
    """
    Track and analyze errors for monitoring and alerting.
    """

    def __init__(self, window_seconds: int = 3600):
        """
        Initialize error tracker.

        Args:
            window_seconds: Time window for error statistics (default 1 hour)
        """
        self.window_seconds = window_seconds
        self._errors: List[ErrorContext] = []

    def record(self, context: ErrorContext):
        """Record an error occurrence."""
        self._errors.append(context)
        self._cleanup_old_errors()

    def _cleanup_old_errors(self):
        """Remove errors outside the time window."""
        cutoff = datetime.now() - timedelta(seconds=self.window_seconds)
        self._errors = [
            e for e in self._errors
            if e.timestamp > cutoff
        ]

    def get_error_count(self, category: Optional[ErrorCategory] = None) -> int:
        """Get count of errors in time window, optionally filtered by category."""
        self._cleanup_old_errors()

        if category is None:
            return len(self._errors)

        return sum(1 for e in self._errors if e.category == category)

    def get_error_rate(self) -> float:
        """Get error rate (errors per second) in the time window."""
        self._cleanup_old_errors()
        return len(self._errors) / max(1, self.window_seconds)

    def should_throttle(self) -> bool:
        """
        Determine if errors are occurring too frequently and operations should be throttled.

        Returns:
            True if error rate exceeds threshold
        """
        # Throttle if more than 10 errors in the last minute
        recent_cutoff = datetime.now() - timedelta(seconds=60)
        recent_errors = [e for e in self._errors if e.timestamp > recent_cutoff]

        return len(recent_errors) > 10

    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics of errors."""
        self._cleanup_old_errors()

        category_counts = {}
        for error in self._errors:
            cat = error.category.value
            category_counts[cat] = category_counts.get(cat, 0) + 1

        severity_counts = {}
        for error in self._errors:
            sev = error.severity.value
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        return {
            "total_errors": len(self._errors),
            "error_rate": self.get_error_rate(),
            "by_category": category_counts,
            "by_severity": severity_counts,
            "should_throttle": self.should_throttle(),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Retry Decorator
# ═══════════════════════════════════════════════════════════════════════════════

def with_retry(
    policy: Optional[RetryPolicy] = None,
    on_retry: Optional[Callable[[ErrorContext, int], None]] = None
):
    """
    Decorator for automatic retry with exponential backoff.

    Args:
        policy: Retry policy configuration
        on_retry: Optional callback called before each retry (context, attempt)
    """
    if policy is None:
        policy = RetryPolicy()

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None

            for attempt in range(policy.max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e

                    # Try to categorize the error
                    context = ErrorContext(
                        message=str(e),
                        details={"exception_type": type(e).__name__}
                    )

                    # Check for Google API errors
                    if hasattr(e, 'resp') and hasattr(e.resp, 'status'):
                        context = categorize_google_api_error(
                            e.resp.status,
                            str(e)
                        )

                    context.retry_count = attempt

                    # Don't retry if not retryable
                    if not context.can_retry:
                        logger.error(f"Non-retryable error: {context.message}")
                        raise

                    # Last attempt, give up
                    if attempt == policy.max_attempts - 1:
                        logger.error(f"Max retries exceeded: {context.message}")
                        raise

                    # Calculate delay
                    delay = policy.get_delay(attempt)

                    logger.warning(
                        f"Retry {attempt + 1}/{policy.max_attempts} after {delay:.1f}s: "
                        f"{context.message}"
                    )

                    if on_retry:
                        on_retry(context, attempt)

                    time.sleep(delay)

            # Should not reach here
            raise last_error

        return wrapper
    return decorator


# ═══════════════════════════════════════════════════════════════════════════════
# Circuit Breaker
# ═══════════════════════════════════════════════════════════════════════════════

class CircuitBreaker:
    """
    Circuit breaker to prevent cascading failures.

    States:
    - CLOSED: Normal operation
    - OPEN: Failing, requests blocked
    - HALF_OPEN: Testing if service recovered
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout_seconds: int = 60,
        half_open_attempts: int = 1
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Failures before opening circuit
            timeout_seconds: Seconds before attempting recovery
            half_open_attempts: Attempts allowed in half-open state
        """
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.half_open_attempts = half_open_attempts

        self._failure_count = 0
        self._last_failure_time = None
        self._state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self._half_open_count = 0

    def call(self, func, *args, **kwargs):
        """
        Execute function through circuit breaker.

        Args:
            func: Function to execute
            *args, **kwargs: Arguments for function

        Returns:
            Function result

        Raises:
            Exception: If circuit is open or function fails
        """
        # Check if circuit should reset
        if self._state == "OPEN":
            elapsed = (datetime.now() - self._last_failure_time).total_seconds()
            if elapsed >= self.timeout_seconds:
                logger.info("Circuit breaker entering HALF_OPEN state")
                self._state = "HALF_OPEN"
                self._half_open_count = 0
            else:
                raise PipelineError(
                    f"Circuit breaker is OPEN. blocking request. "
                    f"Reset in {self.timeout_seconds - elapsed:.0f}s"
                )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        """Handle successful call."""
        if self._state == "HALF_OPEN":
            self._half_open_count += 1
            if self._half_open_count >= self.half_open_attempts:
                logger.info("Circuit breaker closing after successful recovery")
                self._state = "CLOSED"
                self._failure_count = 0
        elif self._state == "CLOSED":
            self._failure_count = 0

    def _on_failure(self):
        """Handle failed call."""
        self._failure_count += 1
        self._last_failure_time = datetime.now()

        if self._failure_count >= self.failure_threshold:
            logger.error(
                f"Circuit breaker opening after {self._failure_count} failures"
            )
            self._state = "OPEN"

    @property
    def state(self) -> str:
        """Get current circuit breaker state."""
        return self._state

    def reset(self):
        """Manually reset circuit breaker."""
        self._state = "CLOSED"
        self._failure_count = 0
        self._last_failure_time = None
        self._half_open_count = 0
