# Video Renderer Package
"""Ubuntu'da intro+loop video birlestirme ve ses miksaji icin moduler renderer."""

__version__ = "2.0.0"
__author__ = "Video Renderer Team"

# Error handling and logging
from .error_reporting import (
    ErrorAggregator,
    ErrorRecord,
    ErrorReportConfig,
    ErrorReportingMode,
    format_error,
    handle_errors,
    report_error,
    safe_execute,
)
from .exceptions import (
    AudioMixingError,
    AudioProcessingError,
    AudioValidationError,
    ErrorContext,
    ErrorSeverity,
    FFmpegCommandError,
    FFmpegError,
    FFmpegNotFoundError,
    FFmpegTimeoutError,
    StateError,
    ValidationError,
    VideoCompatibilityError,
    VideoProcessingError,
    VideoRendererError,
    get_user_message,
    wrap_exception,
)
from .logging import (
    LogContext,
    LogLevel,
    VideoRendererLogger,
    configure_logging,
    generate_request_id,
    generate_session_id,
    get_logger,
    log_errors,
    log_function_call,
    set_context,
)

__all__ = [
    # Exceptions
    "VideoRendererError",
    "FFmpegError",
    "FFmpegNotFoundError",
    "FFmpegCommandError",
    "FFmpegTimeoutError",
    "AudioProcessingError",
    "AudioValidationError",
    "AudioMixingError",
    "VideoProcessingError",
    "VideoCompatibilityError",
    "ValidationError",
    "StateError",
    "ErrorContext",
    "ErrorSeverity",
    "wrap_exception",
    "get_user_message",
    # Logging
    "VideoRendererLogger",
    "LogLevel",
    "LogContext",
    "get_logger",
    "configure_logging",
    "set_context",
    "generate_request_id",
    "generate_session_id",
    "log_function_call",
    "log_errors",
    # Error reporting
    "ErrorAggregator",
    "ErrorReportConfig",
    "ErrorReportingMode",
    "ErrorRecord",
    "handle_errors",
    "safe_execute",
    "format_error",
    "report_error",
]
