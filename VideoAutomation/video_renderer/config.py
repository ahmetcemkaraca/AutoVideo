#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration and constants for video_renderer.
"""

from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Set, Dict, List, Optional
import subprocess
import shutil


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
# Codec Configurations
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
    extra_args: List[str] = field(default_factory=list)
    
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
    preset="6",
    crf=28,
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
    preset="fast",
    crf=23,
    extra_args=["-g", "240", "-tag:v", "hvc1"]
)

# Hardware encoders (NVIDIA)
CODEC_H264_NVENC = CodecConfig(
    name="H.264 (NVENC)",
    encoder="h264_nvenc",
    preset="p4",  # balanced
    crf=23,  # actually uses -cq for NVENC
    profile="high",
    extra_args=["-rc", "vbr", "-cq", "23", "-b:v", "0"]
)

CODEC_H265_NVENC = CodecConfig(
    name="H.265 (NVENC)",
    encoder="hevc_nvenc",
    preset="p4",
    crf=28,
    profile="main",
    extra_args=["-rc", "vbr", "-cq", "28", "-b:v", "0", "-tag:v", "hvc1"]
)

CODEC_AV1_NVENC = CodecConfig(
    name="AV1 (NVENC)",
    encoder="av1_nvenc",
    preset="p4",
    crf=32,
    extra_args=["-rc", "vbr", "-cq", "32", "-b:v", "0"]
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
    preset="",  # VAAPI doesn't use preset
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
# Hardware Acceleration Detection
# ═══════════════════════════════════════════════════════════════════════════════

def detect_available_encoders() -> Dict[str, bool]:
    """Detect available hardware encoders."""
    encoders = {
        "h264_nvenc": False,
        "hevc_nvenc": False,
        "av1_nvenc": False,
        "h264_qsv": False,
        "hevc_qsv": False,
        "h264_vaapi": False,
        "hevc_vaapi": False,
    }
    
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        return encoders
    
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=10
        )
        output = result.stdout
        
        for encoder in encoders:
            if encoder in output:
                encoders[encoder] = True
                
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    return encoders


def get_best_encoder(codec_family: str) -> CodecConfig:
    """Get the best available encoder for a codec family (av1, h264, h265)."""
    available = detect_available_encoders()
    
    if codec_family == "av1":
        if available.get("av1_nvenc"):
            return CODEC_AV1_NVENC
        return CODEC_AV1
    
    elif codec_family == "h264":
        if available.get("h264_nvenc"):
            return CODEC_H264_NVENC
        if available.get("h264_qsv"):
            return CODEC_H264_QSV
        if available.get("h264_vaapi"):
            return CODEC_H264_VAAPI
        return CODEC_H264
    
    elif codec_family == "h265":
        if available.get("hevc_nvenc"):
            return CODEC_H265_NVENC
        if available.get("hevc_qsv"):
            return CODEC_H265_QSV
        if available.get("hevc_vaapi"):
            return CODEC_H265_VAAPI
        return CODEC_H265
    
    return CODEC_H264


# ═══════════════════════════════════════════════════════════════════════════════
# Render Session Configuration
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class RenderConfig:
    """Complete configuration for a render session."""
    # Paths
    work_dir: Path = field(default_factory=Path.cwd)
    music_dir: Optional[Path] = None
    tmp_dir: Optional[Path] = None
    output_path: Optional[Path] = None
    
    # Video settings
    width: int = DEFAULT_WIDTH
    height: int = DEFAULT_HEIGHT
    fps: int = 60
    codec: str = "av1"
    
    # Color
    color: ColorConfig = field(default_factory=lambda: COLOR_BT709)
    
    # Duration
    duration_seconds: int = 0
    
    # Source files
    intro_path: Optional[Path] = None
    loop_path: Optional[Path] = None
    
    # Audio
    tracks: List[Path] = field(default_factory=list)
    backgrounds: List[tuple] = field(default_factory=list)  # List of (Path, dB)
    
    # Post-render action
    post_action: str = "keep"  # keep, archive, delete
    
    # Flags
    use_hw_accel: bool = True
    parallel_encode: bool = True
    
    def __post_init__(self):
        if self.music_dir is None:
            self.music_dir = self.work_dir / "music"
        if self.tmp_dir is None:
            self.tmp_dir = self.work_dir / "tmp"
    
    def get_codec_config(self) -> CodecConfig:
        """Get the codec configuration, preferring HW acceleration if available."""
        if self.use_hw_accel:
            return get_best_encoder(self.codec)
        return CODECS.get(self.codec, CODEC_H264)
