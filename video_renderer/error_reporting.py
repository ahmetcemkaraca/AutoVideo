#!/usr/bin/env python3
"""
Error reporting and aggregation system.

Provides centralized error handling, user-friendly error messages,
debug information management, and error reporting.
"""

import sys
import threading
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import Any

from .exceptions import (
    ErrorSeverity,
    VideoRendererError,
    get_user_message,
)
from .logging import generate_request_id, get_logger

# ═══════════════════════════════════════════════════════════════════════════════
# Error Reporter Configuration
# ═══════════════════════════════════════════════════════════════════════════════


class ErrorReportingMode(Enum):
    """Error reporting modes."""

    SILENT = "silent"  # No user output, log only
    USER_FRIENDLY = "user"  # User-friendly messages only
    DEVELOPER = "developer"  # Detailed error information
    DEBUG = "debug"  # Full debug information with stack traces


@dataclass
class ErrorReportConfig:
    """Configuration for error reporting."""

    mode: ErrorReportingMode = ErrorReportingMode.USER_FRIENDLY
    show_stack_traces: bool = False
    show_technical_details: bool = False
    log_errors: bool = True
    collect_metrics: bool = True
    enable_recovery: bool = True
    max_error_history: int = 100


# ═══════════════════════════════════════════════════════════════════════════════
# Error Record
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class ErrorRecord:
    """Record of an error that occurred."""

    timestamp: datetime
    exception_type: str
    message: str
    user_message: str
    component: str | None
    operation: str | None
    severity: ErrorSeverity
    recovery_possible: bool
    suggested_action: str | None
    stack_trace: str | None
    request_id: str | None
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "exception_type": self.exception_type,
            "message": self.message,
            "user_message": self.user_message,
            "component": self.component,
            "operation": self.operation,
            "severity": (
                self.severity.value if isinstance(self.severity, ErrorSeverity) else self.severity
            ),
            "recovery_possible": self.recovery_possible,
            "suggested_action": self.suggested_action,
            "stack_trace": self.stack_trace,
            "request_id": self.request_id,
            "context": self.context,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Error Aggregator
# ═══════════════════════════════════════════════════════════════════════════════


class ErrorAggregator:
    """
    Centralized error aggregator and reporter.

    Collects errors, maintains error history, and provides
    user-friendly error messages and recovery suggestions.
    """

    def __init__(self, config: ErrorReportConfig | None = None):
        self.config = config or ErrorReportConfig()
        self.logger = get_logger("ErrorAggregator")
        self._error_history: list[ErrorRecord] = []
        self._error_counts: dict[str, int] = {}
        self._lock = threading.Lock()

    def report_error(
        self,
        exception: Exception,
        request_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> ErrorRecord:
        """
        Report an error and create an error record.

        Args:
            exception: Exception that occurred
            request_id: Optional request ID for tracking
            context: Additional context information

        Returns:
            ErrorRecord with error details
        """
        request_id = request_id or generate_request_id()

        # Extract error information
        if isinstance(exception, VideoRendererError):
            error_context = exception.context
            user_message = exception.message
            suggested_action = error_context.user_action
            recovery_possible = error_context.recovery_possible
            severity = error_context.severity
            component = error_context.component
            operation = error_context.operation
        else:
            user_message = get_user_message(exception)
            suggested_action = None
            recovery_possible = False
            severity = ErrorSeverity.ERROR
            component = type(exception).__name__
            operation = None

        # Create error record
        record = ErrorRecord(
            timestamp=datetime.now(),
            exception_type=type(exception).__name__,
            message=str(exception),
            user_message=user_message,
            component=component,
            operation=operation,
            severity=severity,
            recovery_possible=recovery_possible,
            suggested_action=suggested_action,
            stack_trace=traceback.format_exc() if self.config.show_stack_traces else None,
            request_id=request_id,
            context=context or {},
        )

        # Add to history
        with self._lock:
            self._error_history.append(record)

            # Limit history size
            if len(self._error_history) > self.config.max_error_history:
                self._error_history.pop(0)

            # Update error counts
            error_key = f"{record.exception_type}:{record.component or 'unknown'}"
            self._error_counts[error_key] = self._error_counts.get(error_key, 0) + 1

        # Log error
        if self.config.log_errors:
            self.logger.error(
                f"Error reported: {record.exception_type}",
                exception_type=record.exception_type,
                error_message=record.message,
                component=record.component,
                request_id=request_id,
            )

        return record

    def get_user_message(self, record: ErrorRecord) -> str:
        """
        Get user-friendly error message based on reporting mode.

        Args:
            record: Error record

        Returns:
            User-friendly error message
        """
        if self.config.mode == ErrorReportingMode.SILENT:
            return ""

        message_parts = [record.user_message]

        if self.config.mode in (ErrorReportingMode.DEVELOPER, ErrorReportingMode.DEBUG):
            if record.component:
                message_parts.append(f"\n  Component: {record.component}")
            if record.operation:
                message_parts.append(f"  Operation: {record.operation}")

        if self.config.mode == ErrorReportingMode.DEBUG and record.stack_trace:
            message_parts.append(f"\n  Stack trace:\n{record.stack_trace}")

        if record.suggested_action and self.config.enable_recovery:
            message_parts.append(f"\n  Suggested action: {record.suggested_action}")

        return "".join(message_parts)

    def format_error(self, exception: Exception, **kwargs) -> str:
        """
        Format an exception for user display.

        Args:
            exception: Exception to format
            **kwargs: Additional context

        Returns:
            Formatted error message
        """
        record = self.report_error(exception, context=kwargs)
        return self.get_user_message(record)

    def get_error_summary(self) -> dict[str, Any]:
        """
        Get summary of all reported errors.

        Returns:
            Dictionary with error statistics
        """
        with self._lock:
            total = len(self._error_history)
            by_severity = {}
            by_component = {}

            for record in self._error_history:
                severity = (
                    record.severity.value
                    if isinstance(record.severity, ErrorSeverity)
                    else record.severity
                )
                by_severity[severity] = by_severity.get(severity, 0) + 1

                component = record.component or "unknown"
                by_component[component] = by_component.get(component, 0) + 1

            return {
                "total_errors": total,
                "by_severity": by_severity,
                "by_component": by_component,
                "error_counts": dict(self._error_counts),
                "recent_errors": [r.to_dict() for r in self._error_history[-10:]],
            }

    def clear_history(self) -> None:
        """Clear error history."""
        with self._lock:
            self._error_history.clear()
            self._error_counts.clear()

    def get_recent_errors(self, count: int = 10) -> list[ErrorRecord]:
        """
        Get recent error records.

        Args:
            count: Number of recent errors to return

        Returns:
            List of recent error records
        """
        with self._lock:
            return self._error_history[-count:]


# ═══════════════════════════════════════════════════════════════════════════════
# Global Error Aggregator
# ═══════════════════════════════════════════════════════════════════════════════

_global_aggregator: ErrorAggregator | None = None


def get_error_aggregator() -> ErrorAggregator:
    """Get the global error aggregator instance."""
    global _global_aggregator
    if _global_aggregator is None:
        _global_aggregator = ErrorAggregator()
    return _global_aggregator


def configure_error_reporting(config: ErrorReportConfig) -> None:
    """
    Configure global error reporting.

    Args:
        config: Error reporting configuration
    """
    global _global_aggregator
    _global_aggregator = ErrorAggregator(config)


def report_error(exception: Exception, **kwargs) -> ErrorRecord:
    """
    Report an error to the global aggregator.

    Args:
        exception: Exception to report
        **kwargs: Additional context

    Returns:
        ErrorRecord with error details
    """
    return get_error_aggregator().report_error(exception, context=kwargs)


def format_error(exception: Exception, **kwargs) -> str:
    """
    Format an exception for user display.

    Args:
        exception: Exception to format
        **kwargs: Additional context

    Returns:
        Formatted error message
    """
    return get_error_aggregator().format_error(exception, **kwargs)


# ═══════════════════════════════════════════════════════════════════════════════
# Error Handling Decorators
# ═══════════════════════════════════════════════════════════════════════════════


def handle_errors(
    default_return: Any = None,
    raise_on_error: bool = False,
    error_callback: Callable[[Exception], Any] | None = None,
    component: str | None = None,
):
    """
    Decorator to automatically handle and report errors.

    Args:
        default_return: Value to return on error (if not raising)
        raise_on_error: Whether to re-raise the exception
        error_callback: Optional callback to call on error
        component: Component name for error reporting

    Usage:
        @handle_errors(default_return=None, raise_on_error=False)
        def my_function():
            # Function that might raise an exception
            pass
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            aggregator = get_error_aggregator()
            component_name = component or func.__qualname__

            try:
                return func(*args, **kwargs)

            except Exception as e:
                # Report error
                record = aggregator.report_error(
                    e,
                    context={
                        "function": func.__qualname__,
                        "component": component_name,
                    },
                )

                # Call error callback if provided
                if error_callback:
                    error_callback(e)

                # Raise or return default
                if raise_on_error:
                    raise
                return default_return

        return wrapper

    return decorator


def safe_execute(
    func: Callable,
    *args,
    default_return: Any = None,
    raise_on_error: bool = False,
    error_callback: Callable[[Exception], Any] | None = None,
    **kwargs,
) -> Any:
    """
    Safely execute a function with error handling.

    Args:
        func: Function to execute
        *args: Function arguments
        default_return: Value to return on error
        raise_on_error: Whether to re-raise exceptions
        error_callback: Optional error callback
        **kwargs: Function keyword arguments

    Returns:
        Function result or default_return on error
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        report_error(e, function=func.__name__)

        if error_callback:
            error_callback(e)

        if raise_on_error:
            raise
        return default_return


# ═══════════════════════════════════════════════════════════════════════════════
# User-Friendly Error Messages
# ═══════════════════════════════════════════════════════════════════════════════


class ErrorMessage:
    """
    User-friendly error message templates.

    Provides pre-defined error messages for common scenarios
    with suggested actions.
    """

    # File errors
    FILE_NOT_FOUND = (
        "The file '{file}' could not be found.",
        "Check that the file path is correct and the file exists.",
    )

    FILE_NOT_READABLE = (
        "The file '{file}' cannot be read.",
        "Check file permissions and ensure the file is not corrupted.",
    )

    FILE_NOT_WRITABLE = (
        "Cannot write to '{file}'.",
        "Check directory permissions and available disk space.",
    )

    # FFmpeg errors
    FFMPEG_NOT_FOUND = (
        "FFmpeg is not installed or not in PATH.",
        "Install FFmpeg from https://ffmpeg.org/download.html",
    )

    FFMPEG_COMMAND_FAILED = (
        "FFmpeg command failed while processing '{file}'.",
        "Check the file format and try again, or use a different codec.",
    )

    # Video errors
    VIDEO_INCOMPATIBLE = (
        "The video '{file}' is not compatible with target settings.",
        "The video will be re-encoded automatically.",
    )

    VIDEO_ENCODING_FAILED = (
        "Failed to encode video '{file}' with codec '{codec}'.",
        "Try a different codec or check hardware encoder availability.",
    )

    # Audio errors
    AUDIO_CORRUPTED = (
        "The audio file '{file}' appears to be corrupted.",
        "Remove or replace the corrupted file.",
    )

    AUDIO_MIXING_FAILED = (
        "Failed to mix audio tracks.",
        "Ensure all audio files have compatible formats.",
    )

    # Validation errors
    INVALID_DURATION = (
        "Duration must be between {min} and {max} seconds.",
        "Enter a valid duration value.",
    )

    INVALID_RESOLUTION = (
        "Invalid resolution: {resolution}.",
        "Use standard resolutions like 1920x1080 or 3840x2160.",
    )

    # External service errors
    YOUTUBE_AUTH_FAILED = (
        "YouTube authentication failed.",
        "Run --auth-youtube to authenticate with YouTube.",
    )

    YOUTUBE_UPLOAD_FAILED = (
        "Failed to upload video to YouTube.",
        "Check your internet connection and API credentials.",
    )

    DRIVE_UPLOAD_FAILED = (
        "Failed to upload file to Google Drive.",
        "Check your internet connection and API credentials.",
    )

    @staticmethod
    def format(message_template: str, action_template: str, **kwargs) -> str:
        """
        Format an error message with context.

        Args:
            message_template: Error message template
            action_template: Suggested action template
            **kwargs: Template variables

        Returns:
            Formatted error message
        """
        message = message_template.format(**kwargs)
        action = action_template.format(**kwargs)

        if action:
            return f"{message}\n  Suggested action: {action}"
        return message


# ═══════════════════════════════════════════════════════════════════════════════
# Error Recovery System
# ═══════════════════════════════════════════════════════════════════════════════


class RecoveryAction:
    """Base class for error recovery actions."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    def can_recover(self, error: Exception) -> bool:
        """Check if this action can recover from the error."""
        raise NotImplementedError

    def recover(self, error: Exception, context: dict[str, Any]) -> bool:
        """
        Attempt to recover from the error.

        Returns:
            True if recovery was successful
        """
        raise NotImplementedError


class RetryRecovery(RecoveryAction):
    """Recovery action that retries the operation."""

    def __init__(self, max_retries: int = 3):
        super().__init__(
            name="retry", description=f"Retry the operation (up to {max_retries} times)"
        )
        self.max_retries = max_retries

    def can_recover(self, error: Exception) -> bool:
        """Can retry on most errors."""
        return True

    def recover(self, error: Exception, context: dict[str, Any]) -> bool:
        """Retry the operation."""
        retry_count = context.get("retry_count", 0)
        return retry_count < self.max_retries


class FallbackRecovery(RecoveryAction):
    """Recovery action that falls back to alternative method."""

    def __init__(self, fallback_func: Callable, name: str = "fallback"):
        super().__init__(name=name, description=f"Use alternative method: {name}")
        self.fallback_func = fallback_func

    def can_recover(self, error: Exception) -> bool:
        """Can fall back for certain error types."""
        return isinstance(error, (VideoProcessingError, AudioProcessingError))

    def recover(self, error: Exception, context: dict[str, Any]) -> bool:
        """Execute fallback function."""
        try:
            self.fallback_func(**context)
            return True
        except Exception:
            return False


class ErrorRecoveryManager:
    """Manages error recovery strategies."""

    def __init__(self):
        self.recovery_actions: list[RecoveryAction] = []
        self.logger = get_logger("ErrorRecovery")

    def register_action(self, action: RecoveryAction) -> None:
        """Register a recovery action."""
        self.recovery_actions.append(action)

    def attempt_recovery(self, error: Exception, context: dict[str, Any]) -> bool:
        """
        Attempt to recover from an error.

        Args:
            error: Exception that occurred
            context: Recovery context

        Returns:
            True if recovery was successful
        """
        for action in self.recovery_actions:
            if action.can_recover(error):
                self.logger.info(
                    f"Attempting recovery: {action.name}",
                    action=action.name,
                    error_type=type(error).__name__,
                )

                try:
                    if action.recover(error, context):
                        self.logger.info(f"Recovery successful: {action.name}")
                        return True
                except Exception as recovery_error:
                    self.logger.error(f"Recovery failed: {action.name}", exception=recovery_error)

        return False


# Global recovery manager
_recovery_manager: ErrorRecoveryManager | None = None


def get_recovery_manager() -> ErrorRecoveryManager:
    """Get the global recovery manager."""
    global _recovery_manager
    if _recovery_manager is None:
        _recovery_manager = ErrorRecoveryManager()
        # Register default recovery actions
        _recovery_manager.register_action(RetryRecovery())
    return _recovery_manager


# ═══════════════════════════════════════════════════════════════════════════════
# CLI Error Formatting
# ═══════════════════════════════════════════════════════════════════════════════


def format_cli_error(exception: Exception, show_traceback: bool = False) -> str:
    """
    Format an exception for CLI output.

    Args:
        exception: Exception to format
        show_traceback: Whether to show full traceback

    Returns:
        Formatted error string for CLI
    """

    config = ErrorReportConfig(
        mode=ErrorReportingMode.DEBUG if show_traceback else ErrorReportingMode.USER_FRIENDLY,
        show_stack_traces=show_traceback,
    )

    # Temporarily update aggregator config
    aggregator = get_error_aggregator()
    old_config = aggregator.config
    aggregator.config = config

    try:
        message = format_error(exception)
    finally:
        aggregator.config = old_config

    return message


def print_error(exception: Exception, show_traceback: bool = False) -> None:
    """
    Print formatted error to stderr.

    Args:
        exception: Exception to print
        show_traceback: Whether to show full traceback
    """
    message = format_cli_error(exception, show_traceback)
    print(message, file=sys.stderr)
