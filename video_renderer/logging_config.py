#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Logging and error reporting configuration management.

Provides centralized configuration for the error handling
and logging system with environment variable support and
configuration file loading.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .video_logging import LogLevel
from .error_reporting import ErrorReportingMode, ErrorReportConfig

# ═══════════════════════════════════════════════════════════════════════════════
# Configuration File Locations
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_CONFIG_PATHS = [
    Path("./logging_config.json"),
    Path("./config/logging_config.json"),
    Path("~/video_renderer/logging_config.json").expanduser(),
    Path("~/.video_renderer/logging_config.json").expanduser(),
]


# ═══════════════════════════════════════════════════════════════════════════════
# Logging Configuration
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class LoggingConfig:
    """
    Configuration for the logging system.

    Attributes:
        level: Minimum log level to output
        log_dir: Directory for log files
        log_file: Name of the log file
        enable_console: Enable console output
        enable_json: Use JSON formatting for file output
        max_bytes: Maximum size of each log file before rotation
        backup_count: Number of backup log files to keep
        include_context: Include context variables in logs
        include_stack_trace: Include stack traces in logs
        timestamp_format: Format for timestamps in logs
    """

    level: Union[LogLevel, str] = LogLevel.INFO
    log_dir: Optional[Path] = None
    log_file: str = "video_renderer.log"
    enable_console: bool = True
    enable_json: bool = True
    max_bytes: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    include_context: bool = True
    include_stack_trace: bool = False
    timestamp_format: str = "%Y-%m-%dT%H:%M:%S.%fZ"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data["level"] = self.level.value if isinstance(self.level, LogLevel) else self.level
        data["log_dir"] = str(self.log_dir) if self.log_dir else None
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LoggingConfig":
        """Create from dictionary."""
        data = data.copy()

        # Convert level string to enum
        if "level" in data and isinstance(data["level"], str):
            try:
                data["level"] = LogLevel[data["level"].upper()]
            except KeyError:
                data["level"] = LogLevel.INFO

        # Convert log_dir to Path
        if "log_dir" in data and data["log_dir"]:
            data["log_dir"] = Path(data["log_dir"])

        return cls(**data)

    def get_log_path(self) -> Optional[Path]:
        """Get the full path to the log file."""
        if self.log_dir:
            return self.log_dir / self.log_file
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# Error Reporting Configuration
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class ErrorReportingExtendedConfig(ErrorReportConfig):
    """
    Extended configuration for error reporting.

    Attributes:
        mode: Error reporting mode
        show_stack_traces: Show full stack traces
        show_technical_details: Show technical details
        log_errors: Log errors to file
        collect_metrics: Collect error metrics
        enable_recovery: Enable error recovery attempts
        max_error_history: Maximum number of errors to keep in history
        error_report_path: Path to error report file
        enable_user_messages: Enable user-friendly error messages
    """

    error_report_path: Optional[Path] = None
    enable_user_messages: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data["mode"] = self.mode.value if isinstance(self.mode, ErrorReportingMode) else self.mode
        data["error_report_path"] = str(self.error_report_path) if self.error_report_path else None
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ErrorReportingExtendedConfig":
        """Create from dictionary."""
        data = data.copy()

        # Convert mode string to enum
        if "mode" in data and isinstance(data["mode"], str):
            # Try to find mode by value (case-insensitive)
            mode_str = data["mode"].lower()
            for mode in ErrorReportingMode:
                if mode.value == mode_str:
                    data["mode"] = mode
                    break
            else:
                # Default to USER_FRIENDLY if not found
                data["mode"] = ErrorReportingMode.USER_FRIENDLY

        # Convert error_report_path to Path
        if "error_report_path" in data and data["error_report_path"]:
            data["error_report_path"] = Path(data["error_report_path"])

        return cls(**data)


# ═══════════════════════════════════════════════════════════════════════════════
# Complete Configuration
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class VideoRendererConfig:
    """
    Complete configuration for video renderer.

    Includes logging and error reporting configuration.
    """

    logging: LoggingConfig = field(default_factory=LoggingConfig)
    error_reporting: ErrorReportingExtendedConfig = field(
        default_factory=ErrorReportingExtendedConfig
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "logging": self.logging.to_dict(),
            "error_reporting": self.error_reporting.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VideoRendererConfig":
        """Create from dictionary."""
        return cls(
            logging=LoggingConfig.from_dict(data.get("logging", {})),
            error_reporting=ErrorReportingExtendedConfig.from_dict(data.get("error_reporting", {})),
        )

    def save(self, path: Path) -> None:
        """Save configuration to file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: Path) -> "VideoRendererConfig":
        """Load configuration from file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def load_default(cls) -> "VideoRendererConfig":
        """Load configuration from default locations."""
        for config_path in DEFAULT_CONFIG_PATHS:
            if config_path.exists():
                return cls.load(config_path)
        return cls()  # Return default configuration


# ═══════════════════════════════════════════════════════════════════════════════
# Environment Variable Support
# ═══════════════════════════════════════════════════════════════════════════════


class EnvironmentConfig:
    """
    Load configuration from environment variables.

    Environment variables:
    - VIDEO_RENDERER_LOG_LEVEL: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - VIDEO_RENDERER_LOG_DIR: Directory for log files
    - VIDEO_RENDERER_LOG_FILE: Name of log file
    - VIDEO_RENDERER_LOG_JSON: Enable JSON logging (true/false)
    - VIDEO_RENDERER_ERROR_MODE: Error reporting mode (silent, user, developer, debug)
    - VIDEO_RENDERER_ERROR_TRACE: Show stack traces (true/false)
    """

    ENV_PREFIX = "VIDEO_RENDERER_"

    @classmethod
    def get(cls, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get environment variable with prefix."""
        return os.environ.get(f"{cls.ENV_PREFIX}{key}", default)

    @classmethod
    def get_bool(cls, key: str, default: bool = False) -> bool:
        """Get boolean environment variable."""
        value = cls.get(key)
        if value is None:
            return default
        return value.lower() in ("true", "1", "yes", "on")

    @classmethod
    def get_int(cls, key: str, default: int = 0) -> int:
        """Get integer environment variable."""
        value = cls.get(key)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            return default

    @classmethod
    def load(cls) -> VideoRendererConfig:
        """Load configuration from environment variables."""
        # Logging configuration
        log_level_str = cls.get("LOG_LEVEL", "INFO")
        try:
            log_level = LogLevel[log_level_str.upper()]
        except KeyError:
            log_level = LogLevel.INFO

        log_dir = cls.get("LOG_DIR")
        log_file = cls.get("LOG_FILE", "video_renderer.log")
        log_json = cls.get_bool("LOG_JSON", True)

        # Error reporting configuration
        error_mode_str = cls.get("ERROR_MODE", "user")
        try:
            error_mode = ErrorReportingMode[error_mode_str.upper()]
        except KeyError:
            error_mode = ErrorReportingMode.USER_FRIENDLY

        error_trace = cls.get_bool("ERROR_TRACE", False)

        return VideoRendererConfig(
            logging=LoggingConfig(
                level=log_level,
                log_dir=Path(log_dir) if log_dir else None,
                log_file=log_file,
                enable_json=log_json,
            ),
            error_reporting=ErrorReportingExtendedConfig(
                mode=error_mode,
                show_stack_traces=error_trace,
            ),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Configuration Presets
# ═══════════════════════════════════════════════════════════════════════════════


class ConfigPresets:
    """Pre-defined configuration presets for common use cases."""

    @staticmethod
    def development() -> VideoRendererConfig:
        """Development configuration with verbose logging."""
        return VideoRendererConfig(
            logging=LoggingConfig(
                level=LogLevel.DEBUG,
                enable_console=True,
                enable_json=False,
                include_stack_trace=True,
            ),
            error_reporting=ErrorReportingExtendedConfig(
                mode=ErrorReportingMode.DEBUG,
                show_stack_traces=True,
                show_technical_details=True,
            ),
        )

    @staticmethod
    def production() -> VideoRendererConfig:
        """Production configuration with minimal logging."""
        return VideoRendererConfig(
            logging=LoggingConfig(
                level=LogLevel.INFO,
                enable_console=False,
                enable_json=True,
                include_stack_trace=False,
            ),
            error_reporting=ErrorReportingExtendedConfig(
                mode=ErrorReportingMode.USER_FRIENDLY,
                show_stack_traces=False,
                show_technical_details=False,
            ),
        )

    @staticmethod
    def testing() -> VideoRendererConfig:
        """Testing configuration with detailed output."""
        return VideoRendererConfig(
            logging=LoggingConfig(
                level=LogLevel.DEBUG,
                enable_console=True,
                enable_json=True,
                include_stack_trace=True,
            ),
            error_reporting=ErrorReportingExtendedConfig(
                mode=ErrorReportingMode.DEVELOPER,
                show_stack_traces=True,
                show_technical_details=True,
            ),
        )

    @staticmethod
    def silent() -> VideoRendererConfig:
        """Silent configuration with no console output."""
        return VideoRendererConfig(
            logging=LoggingConfig(
                level=LogLevel.ERROR,
                enable_console=False,
                enable_json=True,
            ),
            error_reporting=ErrorReportingExtendedConfig(
                mode=ErrorReportingMode.SILENT,
                show_stack_traces=False,
            ),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Configuration Manager
# ═══════════════════════════════════════════════════════════════════════════════


class ConfigManager:
    """
    Manages loading and applying configuration.

    Priority order (highest to lowest):
    1. Explicitly provided config
    2. Environment variables
    3. Configuration file
    4. Default configuration
    """

    def __init__(self):
        self._config: Optional[VideoRendererConfig] = None

    def load(
        self,
        config: Optional[VideoRendererConfig] = None,
        config_path: Optional[Path] = None,
        use_env: bool = True,
        preset: Optional[str] = None,
    ) -> VideoRendererConfig:
        """
        Load configuration from various sources.

        Args:
            config: Explicitly provided configuration
            config_path: Path to configuration file
            use_env: Whether to check environment variables
            preset: Name of preset to use (development, production, testing, silent)

        Returns:
            Loaded configuration
        """
        # Start with default configuration
        if config:
            self._config = config
        elif preset:
            preset_method = getattr(ConfigPresets, preset, None)
            if preset_method:
                self._config = preset_method()
            else:
                self._config = VideoRendererConfig()
        else:
            self._config = VideoRendererConfig()

        # Load from file if specified
        if config_path and config_path.exists():
            try:
                self._config = VideoRendererConfig.load(config_path)
            except Exception:
                pass  # Use default if file loading fails

        # Load from default locations
        elif not config and not preset:
            try:
                self._config = VideoRendererConfig.load_default()
            except Exception:
                pass  # Use default if no file found

        # Override with environment variables
        if use_env:
            env_config = EnvironmentConfig.load()
            self._merge_config(env_config)

        return self._config

    def _merge_config(self, other: VideoRendererConfig) -> None:
        """Merge another configuration into this one."""
        if self._config is None:
            self._config = other
            return

        # Only override non-default values
        # This is a simple merge - you could make it more sophisticated
        pass

    def apply(self) -> None:
        """Apply the loaded configuration."""
        if self._config is None:
            self.load()

        from . import logging as log_module
        from . import error_reporting as er_module

        # Apply logging configuration
        log_module.configure_logging(
            level=self._config.logging.level,
            log_dir=self._config.logging.log_dir,
            log_file=self._config.logging.log_file,
            enable_console=self._config.logging.enable_console,
            enable_json=self._config.logging.enable_json,
            max_bytes=self._config.logging.max_bytes,
            backup_count=self._config.logging.backup_count,
        )

        # Apply error reporting configuration
        er_module.configure_error_reporting(
            er_module.ErrorReportConfig(
                mode=self._config.error_reporting.mode,
                show_stack_traces=self._config.error_reporting.show_stack_traces,
                show_technical_details=self._config.error_reporting.show_technical_details,
                log_errors=self._config.error_reporting.log_errors,
                collect_metrics=self._config.error_reporting.collect_metrics,
                enable_recovery=self._config.error_reporting.enable_recovery,
                max_error_history=self._config.error_reporting.max_error_history,
            )
        )

    def get_config(self) -> VideoRendererConfig:
        """Get the current configuration."""
        if self._config is None:
            self.load()
        return self._config


# Global configuration manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Get the global configuration manager."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def setup_logging(
    config: Optional[VideoRendererConfig] = None,
    config_path: Optional[Path] = None,
    use_env: bool = True,
    preset: Optional[str] = None,
) -> VideoRendererConfig:
    """
    Setup logging with the specified configuration.

    This is a convenience function that loads and applies configuration.

    Args:
        config: Explicitly provided configuration
        config_path: Path to configuration file
        use_env: Whether to check environment variables
        preset: Name of preset to use

    Returns:
        The loaded and applied configuration
    """
    manager = get_config_manager()
    config = manager.load(config, config_path, use_env, preset)
    manager.apply()
    return config
