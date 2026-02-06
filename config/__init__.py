#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unified Configuration Package for Video Rendering System.

This package consolidates all configuration modules from:
- video_renderer/config.py
- VideoAutomation/automation/config_v2.py
- VideoLivestream/livestream/config.py

Version: 1.0.0
"""

from .base import BaseConfig, ConfigValidationError
from .constants import (
    # File extensions
    VIDEO_EXTENSIONS,
    AUDIO_EXTENSIONS,

    # Video requirements
    DEFAULT_WIDTH,
    DEFAULT_HEIGHT,
    ALLOWED_FPS,

    # Enums
    VideoCodec,
    ColorSpace,
    Preset,
    Profile,

    # Codec configs
    CodecConfig,
    CODEC_AV1,
    CODEC_H264,
    CODEC_H265,
    CODEC_H264_NVENC,
    CODEC_H265_NVENC,
    CODEC_AV1_NVENC,
    CODEC_H264_QSV,
    CODEC_H265_QSV,
    CODEC_H264_VAAPI,
    CODEC_H265_VAAPI,
    CODECS,

    # Color configs
    ColorConfig,
    COLOR_BT709,
    COLOR_BT2020,

    # Privacy status
    PrivacyStatus,
)

from .gpu import (
    GPUConfig,
    RamTestConfig,
    RenderModeConfig,
    get_render_config,
    get_nvenc_extra_args,
    get_hwaccel_input_args,
    get_ramdisk_path,
    setup_temp_directory,
    cleanup_ramdisk,
)

from .renderer import (
    RendererConfig,  # Renamed from RenderConfig to avoid conflict
    detect_available_encoders,
    get_best_encoder,
    clear_encoder_cache,
    # Backward compatibility aliases
    RenderConfig as RendererConfigAlias,
)

from .pipeline import (
    PipelineConfig,
    YouTubeConfig,
    RenderConfig,  # Pipeline's RenderConfig (different from renderer's)
    DEFAULT_CONFIG_TEMPLATE,
    generate_json_schema,
    validate_with_schema,
)

from .livestream import (
    TrackConfig,
    BackgroundConfig,
    PlaylistConfig,
    VideoSet,
    StreamConfig,
    GlobalConfig,
    DEFAULT_CONFIG as DEFAULT_LIVESTREAM_CONFIG,
    generate_playlists,
)

from .validation import (
    validate_config,
    ConfigValidationError as ValidationError,
)

__all__ = [
    # Base
    "BaseConfig",
    "ConfigValidationError",

    # Constants
    "VIDEO_EXTENSIONS",
    "AUDIO_EXTENSIONS",
    "DEFAULT_WIDTH",
    "DEFAULT_HEIGHT",
    "ALLOWED_FPS",

    # Enums
    "VideoCodec",
    "ColorSpace",
    "Preset",
    "Profile",
    "PrivacyStatus",

    # Codec configs
    "CodecConfig",
    "CODEC_AV1",
    "CODEC_H264",
    "CODEC_H265",
    "CODEC_H264_NVENC",
    "CODEC_H265_NVENC",
    "CODEC_AV1_NVENC",
    "CODEC_H264_QSV",
    "CODEC_H265_QSV",
    "CODEC_H264_VAAPI",
    "CODEC_H265_VAAPI",
    "CODECS",

    # Color configs
    "ColorConfig",
    "COLOR_BT709",
    "COLOR_BT2020",

    # GPU/RAM
    "GPUConfig",
    "RamTestConfig",
    "RenderModeConfig",
    "get_render_config",
    "get_nvenc_extra_args",
    "get_hwaccel_input_args",
    "get_ramdisk_path",
    "setup_temp_directory",
    "cleanup_ramdisk",

    # Renderer
    "RendererConfig",
    "detect_available_encoders",
    "get_best_encoder",
    "clear_encoder_cache",

    # Pipeline
    "PipelineConfig",
    "YouTubeConfig",
    "RenderConfig",
    "DEFAULT_CONFIG_TEMPLATE",
    "generate_json_schema",
    "validate_with_schema",

    # Livestream
    "TrackConfig",
    "BackgroundConfig",
    "PlaylistConfig",
    "VideoSet",
    "StreamConfig",
    "GlobalConfig",
    "DEFAULT_LIVESTREAM_CONFIG",
    "generate_playlists",

    # Validation
    "validate_config",
]

__version__ = "1.0.0"
