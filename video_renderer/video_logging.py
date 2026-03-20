#!/usr/bin/env python3
"""
Structured logging system for video renderer.

Provides JSON-formatted logging with context preservation,
multiple output destinations, and log level configuration.
"""

import contextvars
import json
import logging
import logging.handlers
import os
import sys
import threading
import traceback
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

# ═══════════════════════════════════════════════════════════════════════════════
# Context Variables for Request/Session Tracking
# ═══════════════════════════════════════════════════════════════════════════════

# Context variables for tracking requests/sessions across async/coroutine boundaries
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")
session_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("session_id", default="")
user_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("user_id", default="")
component_var: contextvars.ContextVar[str] = contextvars.ContextVar("component", default="")


# ═══════════════════════════════════════════════════════════════════════════════
# Log Level Definitions
# ═══════════════════════════════════════════════════════════════════════════════


class LogLevel(Enum):
    """Log level definitions matching standard logging levels."""

    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


# ═══════════════════════════════════════════════════════════════════════════════
# JSON Formatter
# ═══════════════════════════════════════════════════════════════════════════════


class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging.

    Formats log records as JSON with additional context fields:
    - timestamp: ISO 8601 timestamp
    - level: Log level name
    - logger: Logger name
    - message: Log message
    - module: Python module
    - function: Function name
    - line: Line number
    - request_id: Request tracking ID
    - session_id: Session tracking ID
    - user_id: User tracking ID
    - component: Component name
    - context: Additional context data
    - exception: Exception info if present
    """

    def __init__(
        self,
        include_context: bool = True,
        include_stack_trace: bool = False,
        timestamp_format: str = "%Y-%m-%dT%H:%M:%S.%fZ",
    ):
        super().__init__()
        self.include_context = include_context
        self.include_stack_trace = include_stack_trace
        self.timestamp_format = timestamp_format

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.

        Args:
            record: Log record to format

        Returns:
            JSON-formatted log string
        """
        # Base log data
        log_data: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created).strftime(self.timestamp_format),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "thread": threading.current_thread().name,
            "process": os.getpid(),
        }

        # Add context variables if available
        if self.include_context:
            request_id = request_id_var.get()
            session_id = session_id_var.get()
            user_id = user_id_var.get()
            component = component_var.get()

            if request_id:
                log_data["request_id"] = request_id
            if session_id:
                log_data["session_id"] = session_id
            if user_id:
                log_data["user_id"] = user_id
            if component:
                log_data["component"] = component

        # Add extra fields from record
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
            }

            if self.include_stack_trace:
                log_data["exception"]["traceback"] = self.formatException(record.exc_info)

        # Add stack trace if requested (for debugging)
        if self.include_stack_trace and not record.exc_info:
            log_data["stack_trace"] = "".join(traceback.format_stack())

        return json.dumps(log_data, default=str, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════════════
# Console Formatter (Human-readable)
# ═══════════════════════════════════════════════════════════════════════════════


class ConsoleFormatter(logging.Formatter):
    """
    Human-readable console formatter with colors and symbols.

    Uses ANSI color codes for terminal output.
    """

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",  # Reset
    }

    SYMBOLS = {
        "DEBUG": "🔍",
        "INFO": "ℹ️",
        "WARNING": "⚠️",
        "ERROR": "❌",
        "CRITICAL": "🔥",
    }

    def __init__(self, use_colors: bool = True, use_symbols: bool = True):
        super().__init__()
        self.use_colors = use_colors
        self.use_symbols = use_symbols

    def format(self, record: logging.LogRecord) -> str:
        """Format log record for console output."""
        level = record.levelname
        message = record.getMessage()

        # Build formatted message
        if self.use_colors and self.use_symbols:
            color = self.COLORS.get(level, self.COLORS["RESET"])
            symbol = self.SYMBOLS.get(level, "")
            reset = self.COLORS["RESET"]
            formatted = f"{color}{symbol} [{level}]{reset} {message}"

        elif self.use_symbols:
            symbol = self.SYMBOLS.get(level, "")
            formatted = f"{symbol} [{level}] {message}"

        elif self.use_colors:
            color = self.COLORS.get(level, self.COLORS["RESET"])
            reset = self.COLORS["RESET"]
            formatted = f"{color}[{level}]{reset} {message}"

        else:
            formatted = f"[{level}] {message}"

        # Add context info
        component = component_var.get()
        if component:
            formatted += f" ({component})"

        # Add exception info
        if record.exc_info:
            formatted += f"\n{self.formatException(record.exc_info)}"

        return formatted


# ═══════════════════════════════════════════════════════════════════════════════
# Video Renderer Logger
# ═══════════════════════════════════════════════════════════════════════════════


class VideoRendererLogger:
    """
    Main logger class for video renderer.

    Provides structured logging with context preservation,
    multiple output destinations, and configurable formatting.

    Usage:
        logger = get_logger("VideoEncoder")
        logger.info("Encoding started", video_id="123", codec="h264")
        logger.error("Encoding failed", error=str(e), video_id="123")
    """

    def __init__(
        self,
        name: str,
        level: LogLevel | str = LogLevel.INFO,
        log_file: Path | None = None,
        enable_console: bool = True,
        enable_json: bool = True,
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
    ):
        """
        Initialize logger.

        Args:
            name: Logger name
            level: Log level
            log_file: Optional log file path
            enable_console: Enable console output
            enable_json: Use JSON formatting for file output
            max_bytes: Max size per log file before rotation
            backup_count: Number of backup log files to keep
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(
            level.value if isinstance(level, LogLevel) else logging.getLevelName(level)
        )

        # Clear existing handlers
        self.logger.handlers.clear()

        # Console handler
        if enable_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(ConsoleFormatter())
            self.logger.addHandler(console_handler)

        # File handler
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.handlers.RotatingFileHandler(
                log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
            )

            if enable_json:
                file_handler.setFormatter(JSONFormatter())
            else:
                file_handler.setFormatter(
                    logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
                )

            self.logger.addHandler(file_handler)

    def _add_context(self, extra: dict[str, Any]) -> dict[str, Any]:
        """Add context variables to extra fields."""
        context = {
            "request_id": request_id_var.get(),
            "session_id": session_id_var.get(),
            "user_id": user_id_var.get(),
            "component": component_var.get(),
        }
        context.update(extra)
        return context

    def _log(self, level: int, message: str, **kwargs):
        """Internal logging method."""
        extra_fields = self._add_context(kwargs)

        # Create extra dict for LogRecord
        extra = {"extra_fields": extra_fields}

        self.logger.log(level, message, extra=extra)

    def debug(self, message: str, **kwargs):
        """Log debug message with detailed diagnostic info."""
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs):
        """Log info message for general progress updates."""
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning for non-critical issues."""
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, exception: Exception | None = None, **kwargs):
        """Log error message."""
        if exception:
            kwargs["exception_type"] = type(exception).__name__
            kwargs["exception_message"] = str(exception)

        self._log(logging.ERROR, message, **kwargs)

    def critical(self, message: str, exception: Exception | None = None, **kwargs):
        """Log critical error message."""
        if exception:
            kwargs["exception_type"] = type(exception).__name__
            kwargs["exception_message"] = str(exception)

        self._log(logging.CRITICAL, message, **kwargs)

    def exception(self, message: str, **kwargs):
        """Log exception with full traceback."""
        self.logger.exception(message, extra={"extra_fields": self._add_context(kwargs)})

    # Convenience methods for common operations
    def ffmpeg_command(self, command: list[str], **kwargs):
        """Log FFmpeg command execution."""
        self.info("Executing FFmpeg command", command=" ".join(command), **kwargs)

    def file_operation(self, operation: str, path: Path, **kwargs):
        """Log file operation."""
        self.info(f"File operation: {operation}", path=str(path), **kwargs)

    def progress(self, operation: str, percent: float, **kwargs):
        """Log progress update."""
        self.debug(
            f"Progress: {operation}", operation=operation, percent=f"{percent:.1f}", **kwargs
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Logger Factory and Registry
# ═══════════════════════════════════════════════════════════════════════════════

# Global logger registry
_logger_registry: dict[str, VideoRendererLogger] = {}
_default_log_config = {
    "level": LogLevel.INFO,
    "log_file": None,
    "enable_console": True,
    "enable_json": True,
}


def configure_logging(
    level: LogLevel | str = LogLevel.INFO,
    log_dir: Path | None = None,
    log_file: str | None = None,
    enable_console: bool = True,
    enable_json: bool = True,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
) -> None:
    """
    Configure global logging settings.

    Args:
        level: Log level
        log_dir: Directory for log files
        log_file: Log file name (default: video_renderer.log)
        enable_console: Enable console output
        enable_json: Use JSON formatting
        max_bytes: Max size per log file
        backup_count: Number of backup files
    """
    global _default_log_config

    _default_log_config.update(
        {
            "level": level,
            "enable_console": enable_console,
            "enable_json": enable_json,
            "max_bytes": max_bytes,
            "backup_count": backup_count,
        }
    )

    if log_dir and log_file:
        log_path = log_dir / log_file
    elif log_file:
        log_path = Path(log_file)
    else:
        log_path = None

    _default_log_config["log_file"] = log_path


def get_logger(name: str) -> VideoRendererLogger:
    """
    Get or create a logger instance.

    Args:
        name: Logger name (typically module or class name)

    Returns:
        VideoRendererLogger instance
    """
    if name not in _logger_registry:
        _logger_registry[name] = VideoRendererLogger(name=name, **_default_log_config)
    return _logger_registry[name]


# ═══════════════════════════════════════════════════════════════════════════════
# Context Managers
# ═══════════════════════════════════════════════════════════════════════════════


class LogContext:
    """
    Context manager for setting logging context variables.

    Usage:
        with LogContext(request_id="123", component="VideoEncoder"):
            logger.info("Processing video")
            # All logs in this block will have the context
    """

    def __init__(
        self,
        request_id: str | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
        component: str | None = None,
    ):
        self.tokens = []
        self.context = {
            "request_id": request_id,
            "session_id": session_id,
            "user_id": user_id,
            "component": component,
        }

    def __enter__(self):
        for key, value in self.context.items():
            if value is not None:
                var = globals()[f"{key}_var"]
                self.tokens.append(var.set(value))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for token in self.tokens:
            token.var.reset(token)


def set_context(
    request_id: str | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
    component: str | None = None,
) -> None:
    """
    Set logging context variables for the current scope.

    Use this in functions to set context for all log calls.

    Args:
        request_id: Request ID for tracking
        session_id: Session ID for tracking
        user_id: User ID for tracking
        component: Component name
    """
    if request_id is not None:
        request_id_var.set(request_id)
    if session_id is not None:
        session_id_var.set(session_id)
    if user_id is not None:
        user_id_var.set(user_id)
    if component is not None:
        component_var.set(component)


def generate_request_id() -> str:
    """Generate a unique request ID."""
    return str(uuid.uuid4())


def generate_session_id() -> str:
    """Generate a unique session ID."""
    return str(uuid.uuid4())


# ═══════════════════════════════════════════════════════════════════════════════
# Decorators
# ═══════════════════════════════════════════════════════════════════════════════


def log_function_call(
    logger: VideoRendererLogger | None = None,
    level: LogLevel | str = LogLevel.DEBUG,
    include_args: bool = False,
    include_result: bool = False,
):
    """
    Decorator to log function calls.

    Args:
        logger: Logger instance (uses module logger if not provided)
        level: Log level for the call
        include_args: Include function arguments in log
        include_result: Include return value in log
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            module_logger = logger or get_logger(func.__module__)
            func_name = f"{func.__module__}.{func.__qualname__}"

            log_data = {"function": func_name}

            if include_args:
                log_data["args"] = str(args)
                log_data["kwargs"] = str(kwargs)

            module_logger._log(
                level.value if isinstance(level, LogLevel) else logging.getLevelName(level),
                f"Calling {func_name}",
                **log_data,
            )

            try:
                result = func(*args, **kwargs)

                if include_result:
                    module_logger._log(
                        level.value if isinstance(level, LogLevel) else logging.getLevelName(level),
                        f"Completed {func_name}",
                        function=func_name,
                        result=type(result).__name__,
                    )

                return result

            except Exception as e:
                module_logger.error(f"Error in {func_name}", exception=e, function=func_name)
                raise

        return wrapper

    return decorator


def log_errors(logger: VideoRendererLogger | None = None, reraise: bool = True):
    """
    Decorator to log exceptions in functions.

    Args:
        logger: Logger instance (uses module logger if not provided)
        reraise: Whether to re-raise the exception
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            module_logger = logger or get_logger(func.__module__)
            func_name = f"{func.__module__}.{func.__qualname__}"

            try:
                return func(*args, **kwargs)
            except Exception:
                module_logger.exception(f"Exception in {func_name}", function=func_name)
                if reraise:
                    raise
                return None

        return wrapper

    return decorator


# ═══════════════════════════════════════════════════════════════════════════════
# Log Analysis Utilities
# ═══════════════════════════════════════════════════════════════════════════════


def parse_log_file(log_path: Path) -> list[dict[str, Any]]:
    """
    Parse JSON log file into list of log entries.

    Args:
        log_path: Path to log file

    Returns:
        List of log entry dictionaries
    """
    logs = []

    try:
        with open(log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        log_entry = json.loads(line)
                        logs.append(log_entry)
                    except json.JSONDecodeError:
                        # Skip non-JSON lines
                        continue
    except FileNotFoundError:
        pass

    return logs


def filter_logs(
    logs: list[dict[str, Any]],
    level: str | None = None,
    component: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> list[dict[str, Any]]:
    """
    Filter logs by criteria.

    Args:
        logs: List of log entries
        level: Filter by log level
        component: Filter by component
        start_time: Filter by start time
        end_time: Filter by end time

    Returns:
        Filtered list of log entries
    """
    filtered = logs

    if level:
        filtered = [log for log in filtered if log.get("level") == level]

    if component:
        filtered = [log for log in filtered if log.get("component") == component]

    if start_time:
        filtered = [
            log
            for log in filtered
            if datetime.fromisoformat(log.get("timestamp", "")) >= start_time
        ]

    if end_time:
        filtered = [
            log for log in filtered if datetime.fromisoformat(log.get("timestamp", "")) <= end_time
        ]

    return filtered


def get_error_summary(log_path: Path) -> dict[str, Any]:
    """
    Get summary of errors from log file.

    Args:
        log_path: Path to log file

    Returns:
        Dictionary with error summary
    """
    logs = parse_log_file(log_path)
    error_logs = [log for log in logs if log.get("level") in ("ERROR", "CRITICAL")]

    summary = {
        "total_errors": len(error_logs),
        "by_level": {},
        "by_component": {},
        "recent_errors": error_logs[-10:] if error_logs else [],
    }

    for log in error_logs:
        level = log.get("level", "UNKNOWN")
        component = log.get("component", "unknown")

        summary["by_level"][level] = summary["by_level"].get(level, 0) + 1
        summary["by_component"][component] = summary["by_component"].get(component, 0) + 1

    return summary


# ═══════════════════════════════════════════════════════════════════════════════
# Module-level convenience
# ═══════════════════════════════════════════════════════════════════════════════

# Create default logger
default_logger = get_logger("video_renderer")
