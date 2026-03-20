#!/usr/bin/env python3
"""
Logging filters for sensitive data redaction.

This module provides logging filters that automatically redact sensitive
information such as API keys, tokens, and passwords from log output.
"""

import logging
import re
from re import Pattern


class SensitiveDataFilter(logging.Filter):
    """
    Filter sensitive data from log messages.

    This filter uses regex patterns to detect and redact sensitive information
    including:
    - Bearer tokens
    - OAuth refresh tokens
    - API keys
    - Passwords
    - Client secrets
    - Session IDs
    """

    # Patterns for sensitive data (ordered by specificity)
    SENSITIVE_PATTERNS: list[tuple[str, str]] = [
        # Bearer tokens (RFC 6750)
        (r"Bearer\s+([A-Za-z0-9\-._~+/]+=*)", "Bearer [REDACTED]"),
        # Authorization headers
        (r"Authorization:\s*[A-Za-z]+\s+[A-Za-z0-9\-._~+/]+=*", "Authorization: [REDACTED]"),
        # OAuth refresh tokens
        (
            r'(["\']?)refresh_token\1[\s:]+(["\']?)([A-Za-z0-9\-._~+/]+={0,2})\2',
            r"\1refresh_token\1\2[REDACTED]\2",
        ),
        # OAuth access tokens
        (
            r'(["\']?)access_token\1[\s:]+(["\']?)([A-Za-z0-9\-._~+/]+={0,2})\2',
            r"\1access_token\1\2[REDACTED]\2",
        ),
        # API keys (common patterns)
        (
            r'(["\']?)(?:api[_-]?key|apikey)\1[\s:]+(["\']?)([A-Za-z0-9\-_]{20,})\2',
            r"\1\1\2[REDACTED]\2",
        ),
        # Client secrets
        (
            r'(["\']?)(?:client[_-]?secret|clientsecret)\1[\s:]+(["\']?)([A-Za-z0-9\-_.]{20,})\2',
            r"\1\1\2[REDACTED]\2",
        ),
        # Passwords in URLs
        (r"://([^:]+):([^@]+)@", r"://\1:[REDACTED]@"),
        # Password fields
        (r'(["\']?)(?:password|passwd|pwd)\1[\s:]+(["\']?)([^\s"\']{4,})\2', r"\1\1\2[REDACTED]\2"),
        # Session IDs (hex strings)
        (r'(["\']?)session[_-]?id\1[\s:]+(["\']?)([0-9a-fA-F]{16,})\2', r"\1\1\2[REDACTED]\2"),
        # JWT tokens (matches header.payload.signature format)
        (r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "[JWT_REDACTED]"),
        # Generic token patterns
        (r'(["\']?)token\1[\s:]+(["\']?)([A-Za-z0-9\-._~+/]{20,}={0,2})\2', r"\1\1\2[REDACTED]\2"),
    ]

    def __init__(self, patterns: list[tuple[str, str]] | None = None):
        """
        Initialize the sensitive data filter.

        Args:
            patterns: Optional list of (pattern, replacement) tuples.
                     If not provided, uses default SENSITIVE_PATTERNS.
        """
        super().__init__()
        self.patterns = patterns or self.SENSITIVE_PATTERNS
        self._compiled_patterns: list[tuple[Pattern, str]] = [
            (re.compile(pattern), replacement) for pattern, replacement in self.patterns
        ]

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filter and redact sensitive data from a log record.

        Args:
            record: The log record to filter

        Returns:
            True (always allows the record after redaction)
        """
        # Redact from the message
        if isinstance(record.msg, str):
            record.msg = self._redact(record.msg)

        # Redact from args
        if record.args:
            record.args = tuple(
                self._redact(str(arg)) if isinstance(arg, str) else arg for arg in record.args
            )

        return True

    def _redact(self, text: str) -> str:
        """
        Apply redaction patterns to text.

        Args:
            text: Text to redact

        Returns:
            Redacted text
        """
        for pattern, replacement in self._compiled_patterns:
            text = pattern.sub(replacement, text)
        return text

    def add_pattern(self, pattern: str, replacement: str = "[REDACTED]") -> None:
        """
        Add a custom redaction pattern.

        Args:
            pattern: Regex pattern to match
            replacement: Replacement string (default: [REDACTED])
        """
        self.patterns.append((pattern, replacement))
        self._compiled_patterns.append((re.compile(pattern), replacement))


class PathRedactionFilter(logging.Filter):
    """
    Filter to redact sensitive paths from log messages.

    This filter removes or redacts paths that may contain sensitive
    information like usernames or system details.
    """

    def __init__(self, base_paths: list[str] | None = None, replacement: str = "[PATH]"):
        """
        Initialize the path redaction filter.

        Args:
            base_paths: List of base paths to redact (default: auto-detected)
            replacement: Replacement string for redacted paths
        """
        super().__init__()
        self.replacement = replacement
        self.base_paths = base_paths or self._detect_base_paths()
        self._compiled_patterns = self._compile_patterns()

    def _detect_base_paths(self) -> list[str]:
        """
        Detect common base paths that should be redacted.

        Returns:
            List of base paths to redact
        """
        import os
        from pathlib import Path

        paths = []

        # Home directory
        home = str(Path.home())
        if home:
            paths.append(home)

        # Current directory
        cwd = str(Path.cwd())
        if cwd:
            paths.append(cwd)

        # User profile (Windows)
        if os.name == "nt":
            userprofile = os.environ.get("USERPROFILE")
            if userprofile:
                paths.append(userprofile)

        return paths

    def _compile_patterns(self) -> list[Pattern]:
        """
        Compile regex patterns for path redaction.

        Returns:
            List of compiled regex patterns
        """
        patterns = []

        for base_path in self.base_paths:
            # Escape special regex characters in path
            escaped = re.escape(base_path)
            # Match the path with optional trailing components
            pattern = re.compile(rf"{escaped}[\\/][^\s]*")
            patterns.append(pattern)

        return patterns

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Redact sensitive paths from log record.

        Args:
            record: The log record to filter

        Returns:
            True (always allows the record after redaction)
        """
        if isinstance(record.msg, str):
            for pattern in self._compiled_patterns:
                record.msg = pattern.sub(self.replacement, record.msg)

        return True


def setup_sensitive_data_logging(logger: logging.Logger, level: int = logging.INFO) -> None:
    """
    Configure a logger with sensitive data filtering.

    This is a convenience function to quickly set up secure logging.

    Args:
        logger: Logger instance to configure
        level: Logging level (default: INFO)
    """
    # Add sensitive data filter
    sensitive_filter = SensitiveDataFilter()
    logger.addFilter(sensitive_filter)

    # Add path redaction filter
    path_filter = PathRedactionFilter()
    logger.addFilter(path_filter)

    # Set level
    logger.setLevel(level)


def get_sensitive_data_filter() -> SensitiveDataFilter:
    """
    Get a pre-configured sensitive data filter instance.

    Returns:
        SensitiveDataFilter instance with default patterns
    """
    return SensitiveDataFilter()


def get_path_redaction_filter() -> PathRedactionFilter:
    """
    Get a pre-configured path redaction filter instance.

    Returns:
        PathRedactionFilter instance with auto-detected base paths
    """
    return PathRedactionFilter()
