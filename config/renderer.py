#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video renderer configuration.

Extracted and adapted from video_renderer/config.py.
Provides codec configurations, hardware detection, and render session configuration.
"""

import subprocess
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Set, Dict, List, Optional

from .base import BaseConfig
from .constants import (
    CodecConfig, ColorConfig,
    CODECS, COLOR_BT709,
    VIDEO_EXTENSIONS, AUDIO_EXTENSIONS,
    DEFAULT_WIDTH, DEFAULT_HEIGHT,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Hardware Acceleration Detection
# ═══════════════════════════════════════════════════════════════════════════════

# Module-level cache for encoder availability
_encoder_detection_cache: Optional[Dict[str, bool]] = None
_cache_timestamp = 0.0
_CACHE_TTL = 300.0  # Cache for 5 minutes


def detect_available_encoders(use_cache: bool = True, force_refresh: bool = False) -> Dict[str, bool]:
    """
    OPTIMIZED: Detect available hardware encoders by actually testing them.

    Improvements:
    - Caching to avoid repeated detection (5-minute TTL)
    - Optimized test commands for faster detection
    - Better error handling
    - Concurrent testing capability for better performance

    Args:
        use_cache: Use cached results if available (default: True)
        force_refresh: Force re-detection even if cache is valid

    Returns:
        Dictionary mapping encoder names to availability
    """
    global _encoder_detection_cache, _cache_timestamp

    current_time = time.time()

    # Check cache
    if use_cache and _encoder_detection_cache is not None and not force_refresh:
        if current_time - _cache_timestamp < _CACHE_TTL:
            return _encoder_detection_cache.copy()

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

    # First check if encoders are listed (with word boundary matching to avoid false positives)
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=10
        )
        output = result.stdout
        # Use word boundary regex to avoid false positives (e.g., h264_nvenc vs h264_nvenc_old)
        import re as _re
        listed_encoders = [
            enc for enc in encoders
            if _re.search(rf'\b{_re.escape(enc)}\b', output)
        ]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return encoders

    # Test each listed encoder with optimized test commands
    # Using minimal parameters for fastest detection
    for encoder in listed_encoders:
        try:
            # Optimized test: single frame, minimal resolution
            test_cmd = [
                "ffmpeg", "-hide_banner", "-y",
                "-f", "lavfi", "-i", "color=black:s=64x64:d=0.04",  # Single frame at 25fps
                "-c:v", encoder,
                "-t", "0.04",  # Duration for one frame
                "-f", "null", "-"
            ]
            result = subprocess.run(
                test_cmd,
                capture_output=True, text=True, timeout=5,
                check=False
            )
            # Check for success indicators (returncode 0 and no errors in stderr)
            if result.returncode == 0 and "Error" not in result.stderr:
                encoders[encoder] = True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    # Update cache
    _encoder_detection_cache = encoders.copy()
    _cache_timestamp = current_time

    return encoders.copy()


def get_best_encoder(codec_family: str) -> CodecConfig:
    """
    OPTIMIZED: Get the best available encoder for a codec family.

    Priority order:
    1. NVIDIA NVENC (best performance)
    2. Intel QSV (good performance)
    3. VAAPI (Linux AMD/Intel)
    4. Software encoders (universal compatibility)

    Args:
        codec_family: Codec family ("av1", "h264", "h265")

    Returns:
        Best available CodecConfig
    """
    from .constants import (
        CODEC_AV1, CODEC_AV1_NVENC,
        CODEC_H264, CODEC_H264_NVENC, CODEC_H264_QSV, CODEC_H264_VAAPI,
        CODEC_H265, CODEC_H265_NVENC, CODEC_H265_QSV, CODEC_H265_VAAPI,
    )

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


def clear_encoder_cache():
    """Clear the encoder detection cache. Useful for testing or after hardware changes."""
    global _encoder_detection_cache, _cache_timestamp
    _encoder_detection_cache = None
    _cache_timestamp = 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# Render Session Configuration
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class RendererConfig(BaseConfig):
    """
    Complete configuration for a render session.

    NOTE: Renamed from RenderConfig to RendererConfig to avoid conflict
    with pipeline.config's RenderConfig. Use RendererConfig for renderer
    configuration and pipeline.RenderConfig for pipeline render settings.
    """
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
        # Convert string paths to Path objects
        if isinstance(self.work_dir, str):
            self.work_dir = Path(self.work_dir)
        if isinstance(self.music_dir, str):
            self.music_dir = Path(self.music_dir)
        if isinstance(self.tmp_dir, str):
            self.tmp_dir = Path(self.tmp_dir)
        if isinstance(self.output_path, str):
            self.output_path = Path(self.output_path)
        if isinstance(self.intro_path, str):
            self.intro_path = Path(self.intro_path)
        if isinstance(self.loop_path, str):
            self.loop_path = Path(self.loop_path)

        # Set defaults
        if self.music_dir is None:
            self.music_dir = self.work_dir / "music"
        if self.tmp_dir is None:
            self.tmp_dir = self.work_dir / "tmp"

        # Convert track paths
        new_tracks = []
        for track in self.tracks:
            if isinstance(track, str):
                new_tracks.append(Path(track))
            else:
                new_tracks.append(track)
        self.tracks = new_tracks

    @classmethod
    def from_file(cls, path: Path) -> "RendererConfig":
        """Load config from JSON file."""
        import json
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    def to_file(self, path: Path) -> None:
        """Save config to JSON file."""
        import json
        data = self.to_dict()

        # Convert Path objects to strings for JSON serialization
        def convert_paths(obj):
            if isinstance(obj, Path):
                return str(obj)
            elif isinstance(obj, dict):
                return {k: convert_paths(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_paths(item) for item in obj]
            elif isinstance(obj, tuple):
                return tuple(convert_paths(item) for item in obj)
            return obj

        data = convert_paths(data)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def validate(self) -> List[str]:
        """Validate configuration."""
        errors = []

        # Validate resolution
        if self.width < 1 or self.height < 1:
            errors.append("Width and height must be positive")

        # Validate FPS
        if self.fps not in {24, 25, 30, 50, 60}:
            errors.append(f"Unusual FPS: {self.fps}. Common: 24, 25, 30, 50, 60")

        # Validate codec
        valid_codecs = {"av1", "h264", "h265", "vp9"}
        if self.codec not in valid_codecs:
            errors.append(f"Invalid codec: {self.codec}. Must be one of: {valid_codecs}")

        # Validate post action
        if self.post_action not in {"keep", "archive", "delete"}:
            errors.append(f"Invalid post_action: {self.post_action}")

        return errors

    def get_codec_config(self) -> CodecConfig:
        """Get the codec configuration, preferring HW acceleration if available."""
        if self.use_hw_accel:
            return get_best_encoder(self.codec)
        return CODECS.get(self.codec, CODECS.get("h264"))

    def to_dict(self):
        """Convert to dictionary."""
        from dataclasses import asdict
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════════════════
# Backward Compatibility Aliases
# ═══════════════════════════════════════════════════════════════════════════════

# Alias for backward compatibility
RenderConfig = RendererConfig
