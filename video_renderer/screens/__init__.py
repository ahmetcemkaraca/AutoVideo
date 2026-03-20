#!/usr/bin/env python3
"""
Screens package for Video Renderer TUI.
"""

from .audio_select import AudioSelectScreen
from .batch import BatchScreen
from .complete import CompleteScreen
from .home import HomeScreen
from .mode_select import ModeSelectScreen
from .render import RenderScreen
from .settings import SettingsScreen
from .smart_batch import SmartBatchScreen

# Import from validation (pre/post-render validation display)
from .validation import ValidationScreen as RenderValidationScreen
from .validation import (
    show_validation_result,
)

# Import from validation_screen (file validation display)
from .validation_screen import (
    ValidationReport,
)
from .validation_screen import ValidationResult as FileValidationResult
from .validation_screen import ValidationScreen as FileValidationScreen
from .video_select import VideoSelectScreen

__all__ = [
    "HomeScreen",
    "ModeSelectScreen",
    "VideoSelectScreen",
    "AudioSelectScreen",
    "SettingsScreen",
    "RenderScreen",
    "CompleteScreen",
    "BatchScreen",
    "SmartBatchScreen",
    # File validation (validation_screen.py)
    "FileValidationScreen",
    "ValidationReport",
    "FileValidationResult",
    # Render validation (validation.py)
    "RenderValidationScreen",
    "show_validation_result",
]
