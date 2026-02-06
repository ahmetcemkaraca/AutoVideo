#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Base configuration classes for the unified config system.

Provides abstract base classes and common interfaces for all configuration types.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Any, Dict
import json


class ConfigValidationError(Exception):
    """Configuration validation error."""

    def __init__(self, message: str, field: str = None, value: Any = None):
        super().__init__(message)
        self.field = field
        self.value = value


class BaseConfig(ABC):
    """
    Abstract base class for all configuration types.

    All config classes must inherit from this and implement:
    - from_file(): Load config from file
    - to_file(): Save config to file
    - validate(): Validate configuration
    """

    @classmethod
    @abstractmethod
    def from_file(cls, path: Path) -> "BaseConfig":
        """
        Load configuration from file.

        Args:
            path: Path to configuration file

        Returns:
            Configuration instance
        """
        pass

    @abstractmethod
    def to_file(self, path: Path) -> None:
        """
        Save configuration to file.

        Args:
            path: Path to save configuration
        """
        pass

    @abstractmethod
    def validate(self) -> List[str]:
        """
        Validate configuration.

        Returns:
            List of validation errors (empty if valid)
        """
        pass

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary.

        Returns:
            Dictionary representation of config
        """
        from dataclasses import asdict
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaseConfig":
        """
        Create configuration from dictionary.

        Args:
            data: Dictionary with configuration data

        Returns:
            Configuration instance
        """
        return cls(**data)
