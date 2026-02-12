#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Constants and enums for the unified configuration system.

Extracted from:
- video_renderer/config.py
- VideoAutomation/automation/config_v2.py
"""

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from typing import Set, Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════════════════
# File Extensions
# ═══════════════════════════════════════════════════════════════════════════════

VIDEO_EXTENSIONS: Set[str] = {".mp4", ".mkv", ".mov", ".m4v", ".webm", ".avi"}
AUDIO_EXTENSIONS: Set[str] = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".wma"}


# ═══════════════════════════════════════════════════════════════════════════════
# Video Requirements
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_WIDTH = 1920
DEFAULT_HEIGHT = 1080
ALLOWED_FPS: Set[Fraction] = {Fraction(60, 1), Fraction(60000, 1001)}  # 60 or 59.94


# ═══════════════════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════════════════

class VideoCodec(str, Enum):
    """Supported video codecs."""
    H264 = "h264"
    H265 = "h265"
    VP9 = "vp9"
    AV1 = "av1"


class ColorSpace(str, Enum):
    """Color space standards."""
    BT709 = "bt709"
    BT2020 = "bt2020"


class Preset(str, Enum):
    """FFmpeg encoder presets."""
    ULTRAFAST = "ultrafast"
    SUPERFAST = "superfast"
    VERYFAST = "veryfast"
    FASTER = "faster"
    FAST = "fast"
    MEDIUM = "medium"
    SLOW = "slow"
    SLOWER = "slower"
    VERYSLOW = "veryslow"


class Profile(str, Enum):
    """GPU/RAM optimization profiles."""
    STANDARD = "standard"
    HIGH_VRAM = "high_vram"
    ULTRA = "ultra"


class PrivacyStatus(Enum):
    """YouTube video privacy status."""
    PUBLIC = "public"
    PRIVATE = "private"
    UNLISTED = "unlisted"


# ═══════════════════════════════════════════════════════════════════════════════
# Codec Configuration Classes
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class CodecConfig:
    """Configuration for a video codec."""
    name: str
    encoder: str
    preset: str
    crf: int
    profile: Optional[str] = None
    level: Optional[str] = None
    extra_args: List[str] = None
    codec_family: str = "h264"  # Default codec family

    def __post_init__(self):
        if self.extra_args is None:
            self.extra_args = []

        # Auto-detect codec_family from encoder if not explicitly set
        if self.codec_family == "h264":
            # Default, already set
            pass
        elif "av1" in self.encoder.lower():
            self.codec_family = "av1"
        elif "h265" in self.encoder.lower() or "hevc" in self.encoder.lower():
            self.codec_family = "h265"
        elif "h264" in self.encoder.lower():
            self.codec_family = "h264"

    def to_ffmpeg_args(self) -> List[str]:
        """Convert config to FFmpeg arguments."""
        args = ["-c:v", self.encoder, "-preset", self.preset, "-crf", str(self.crf)]
        if self.profile:
            args += ["-profile:v", self.profile]
        if self.level:
            args += ["-level", self.level]
        args += self.extra_args
        return args


# Software encoders
CODEC_AV1 = CodecConfig(
    name="AV1",
    encoder="libsvtav1",
    preset="8",
    crf=36,
    extra_args=["-g", "240"]
)

CODEC_H264 = CodecConfig(
    name="H.264",
    encoder="libx264",
    preset="fast",
    crf=20,
    profile="high",
    level="4.2",
    extra_args=["-g", "240", "-tune", "film"]
)

CODEC_H265 = CodecConfig(
    name="H.265",
    encoder="libx265",
    preset="slow",
    crf=32,
    extra_args=["-g", "240", "-tag:v", "hvc1"]
)

# Hardware encoders (NVIDIA)
CODEC_H264_NVENC = CodecConfig(
    name="H.264 (NVENC)",
    encoder="h264_nvenc",
    preset="p6",
    crf=23,
    profile="high",
    extra_args=[
        "-rc", "vbr", "-cq", "23", "-b:v", "0",
        "-spatial_aq", "1",
        "-b_ref_mode", "0",
        "-rc-lookahead", "32",
        "-surfaces", "64",
        "-extra_hw_frames", "8"
    ]
)

CODEC_H265_NVENC = CodecConfig(
    name="H.265 (NVENC)",
    encoder="hevc_nvenc",
    preset="p6",
    crf=35,
    profile="main",
    extra_args=[
        "-rc", "vbr", "-cq", "35", "-b:v", "0",
        "-tag:v", "hvc1", "-spatial_aq", "1",
        "-b_ref_mode", "0",
        "-rc-lookahead", "32",
        "-surfaces", "64",
        "-extra_hw_frames", "8"
    ]
)

CODEC_AV1_NVENC = CodecConfig(
    name="AV1 (NVENC)",
    encoder="av1_nvenc",
    preset="p6",
    crf=50,
    extra_args=[
        "-rc", "vbr", "-cq", "50", "-b:v", "0",
        "-spatial_aq", "1",
        "-b_ref_mode", "0",
        "-rc-lookahead", "32",
        "-surfaces", "64",
        "-extra_hw_frames", "8"
    ]
)

# Hardware encoders (Intel QSV)
CODEC_H264_QSV = CodecConfig(
    name="H.264 (QSV)",
    encoder="h264_qsv",
    preset="medium",
    crf=23,
    profile="high",
    extra_args=["-global_quality", "23"]
)

CODEC_H265_QSV = CodecConfig(
    name="H.265 (QSV)",
    encoder="hevc_qsv",
    preset="medium",
    crf=28,
    extra_args=["-global_quality", "28", "-tag:v", "hvc1"]
)

# Hardware encoders (VAAPI - AMD/Intel on Linux)
CODEC_H264_VAAPI = CodecConfig(
    name="H.264 (VAAPI)",
    encoder="h264_vaapi",
    preset="",
    crf=23,
    profile="high",
    extra_args=["-qp", "23"]
)

CODEC_H265_VAAPI = CodecConfig(
    name="H.265 (VAAPI)",
    encoder="hevc_vaapi",
    preset="",
    crf=28,
    extra_args=["-qp", "28", "-tag:v", "hvc1"]
)


# Codec registry
CODECS: Dict[str, CodecConfig] = {
    "av1": CODEC_AV1,
    "h264": CODEC_H264,
    "h265": CODEC_H265,
    "h264_nvenc": CODEC_H264_NVENC,
    "h265_nvenc": CODEC_H265_NVENC,
    "av1_nvenc": CODEC_AV1_NVENC,
    "h264_qsv": CODEC_H264_QSV,
    "h265_qsv": CODEC_H265_QSV,
    "h264_vaapi": CODEC_H264_VAAPI,
    "h265_vaapi": CODEC_H265_VAAPI,
}


# ═══════════════════════════════════════════════════════════════════════════════
# Color Space Configuration
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ColorConfig:
    """Color space configuration."""
    colorspace: str
    color_primaries: str
    color_trc: str

    def to_ffmpeg_args(self) -> List[str]:
        return [
            "-colorspace", self.colorspace,
            "-color_primaries", self.color_primaries,
            "-color_trc", self.color_trc
        ]


COLOR_BT709 = ColorConfig("bt709", "bt709", "bt709")
COLOR_BT2020 = ColorConfig("bt2020nc", "bt2020", "bt2020-10")


# ═══════════════════════════════════════════════════════════════════════════════
# YouTube Constants
# ═══════════════════════════════════════════════════════════════════════════════

YOUTUBE_CATEGORIES = {
    "music": "10",
    "entertainment": "24",
    "people_blogs": "22",
    "gaming": "20",
    "howto": "26",
    "news": "25",
    "sports": "17"
}

# Additional audio/video formats for pipeline
PIPELINE_AUDIO_FORMATS = {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"}
PIPELINE_VIDEO_FORMATS = {".mp4", ".mkv", ".mov", ".avi", ".webm"}
