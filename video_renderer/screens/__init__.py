#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Screens package for Video Renderer TUI.
"""

from .home import HomeScreen
from .mode_select import ModeSelectScreen
from .video_select import VideoSelectScreen
from .audio_select import AudioSelectScreen
from .settings import SettingsScreen
from .render import RenderScreen
from .complete import CompleteScreen
from .batch import BatchScreen
from .smart_batch import SmartBatchScreen

# Import from validation_screen (file validation display)
from .validation_screen import (
    ValidationScreen as FileValidationScreen,
    ValidationReport,
    ValidationResult as FileValidationResult,
)

# Import from validation (pre/post-render validation display)
from .validation import (
    ValidationScreen as RenderValidationScreen,
    show_validation_result,
)

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
