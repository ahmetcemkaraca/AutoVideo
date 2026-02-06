#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration and constants for video_renderer.

Includes both standard and RAM-optimized (ramtest) configurations.
"""

from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Set, Dict, List, Optional
import subprocess
import shutil
import os


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
    preset="p6",  # slower, better quality
    crf=23,  # actually uses -cq for NVENC
    profile="high",
    extra_args=[
        "-rc", "vbr", "-cq", "23", "-b:v", "0",
        "-spatial_aq", "1",
        "-b_ref_mode", "0",        # Disable B-frame ref for faster encode
        "-rc-lookahead", "32",     # Lookahead frames for better quality
        "-surfaces", "64",         # Async depth for GPU utilization
        "-extra_hw_frames", "8"    # Extra frames for pipeline
    ]
)

CODEC_H265_NVENC = CodecConfig(
    name="H.265 (NVENC)",
    encoder="hevc_nvenc",
    preset="p6",
    crf=26,
    profile="main",
    extra_args=[
        "-rc", "vbr", "-cq", "26", "-b:v", "0",
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
    crf=40,
    extra_args=[
        "-rc", "vbr", "-cq", "40", "-b:v", "0",
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

    import time
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
                capture_output=True, text=True, timeout=5,  # Increased from 3 to reduce false negatives
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


# ═══════════════════════════════════════════════════════════════════════════════
# RAM/VRAM Optimized Configuration (from ramtest)
# ═══════════════════════════════════════════════════════════════════════════════

# RAM Disk Configuration
# On Linux, /dev/shm is a tmpfs mount (RAM-based)
# Typical size is half of RAM

def get_ramdisk_path() -> Optional[Path]:
    """Get RAM disk path if available and has sufficient space."""

    # Linux tmpfs
    shm_path = Path("/dev/shm")
    if shm_path.exists() and shm_path.is_dir():
        # Check available space (need at least 10GB for temp files)
        try:
            stat = os.statvfs(str(shm_path))
            free_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)
            if free_gb >= 10:
                return shm_path / "video_render_tmp"
        except Exception:
            pass

    # Fallback to regular temp
    return None


def setup_temp_directory(base_dir: Path, use_ramdisk: bool = True) -> Path:
    """
    Setup temp directory, preferring RAM disk if available and requested.

    Args:
        base_dir: Project base directory (fallback location)
        use_ramdisk: Whether to try using RAM disk

    Returns:
        Path to temp directory
    """
    # Try RAM disk first if requested
    if use_ramdisk:
        ramdisk = get_ramdisk_path()
        if ramdisk:
            ramdisk.mkdir(parents=True, exist_ok=True)
            print(f"[RAM] Temp files kullanilacak: {ramdisk}")
            return ramdisk

    # Fallback to local tmp
    local_tmp = base_dir / "tmp"
    local_tmp.mkdir(parents=True, exist_ok=True)
    print(f"[DISK] Temp files kullanilacak: {local_tmp}")
    return local_tmp


def cleanup_ramdisk():
    """Clean up RAM disk temp files."""
    ramdisk = get_ramdisk_path()
    if ramdisk and ramdisk.exists():
        try:
            shutil.rmtree(ramdisk)
            print("[RAM] Temp dosyalar temizlendi.")
        except Exception as e:
            print(f"[WARNING] RAM cleanup hatasi: {e}")


# GPU Buffer Configuration for high-VRAM systems
GPU_CONFIG = {
    # NVENC surfaces for async encoding
    "surfaces": 128,        # Increased from 64

    # Extra hardware frames in pipeline
    "extra_hw_frames": 16,  # Increased from 8

    # Lookahead frames
    "rc_lookahead": 48,     # Increased from 32

    # Decode buffer
    "decode_surfaces": 32,  # For hwaccel decode
}


def get_nvenc_extra_args(codec_family: str = "av1", high_vram: bool = False) -> list:
    """
    Get optimized NVENC arguments.

    Args:
        codec_family: "av1", "h264", or "h265"
        high_vram: Use high-VRAM optimization (20GB+)

    Returns:
        List of FFmpeg arguments
    """
    if high_vram:
        base_args = [
            "-rc", "vbr",
            "-spatial_aq", "1",
            "-b_ref_mode", "0",
            "-rc-lookahead", str(GPU_CONFIG["rc_lookahead"]),
            "-surfaces", str(GPU_CONFIG["surfaces"]),
            "-extra_hw_frames", str(GPU_CONFIG["extra_hw_frames"]),
        ]
    else:
        base_args = [
            "-rc", "vbr",
            "-spatial_aq", "1",
            "-b_ref_mode", "0",
            "-rc-lookahead", "32",
            "-surfaces", "64",
            "-extra_hw_frames", "8"
        ]

    if codec_family == "av1":
        base_args.extend(["-cq", "30", "-b:v", "0"])
    elif codec_family == "h265":
        base_args.extend(["-cq", "26", "-b:v", "0", "-tag:v", "hvc1"])
    else:  # h264
        base_args.extend(["-cq", "23", "-b:v", "0"])

    return base_args


def get_hwaccel_input_args(high_vram: bool = False) -> list:
    """Get hardware acceleration input arguments for decoding."""
    if high_vram:
        return [
            "-hwaccel", "cuda",
            "-hwaccel_output_format", "cuda",
            "-extra_hw_frames", str(GPU_CONFIG["decode_surfaces"]),
        ]
    return [
        "-hwaccel", "cuda",
        "-hwaccel_output_format", "cuda",
    ]


# Memory limits for chunked processing
CHUNK_CONFIG = {
    # Max chunk duration in seconds (2 hours)
    "max_chunk_duration": 7200,

    # Minimum RAM for chunked mode (GB)
    "min_ram_for_full": 64,

    # Enable chunked mode automatically for videos longer than this (hours)
    "auto_chunk_threshold_hours": 12,
}


@dataclass
class RamTestConfig:
    """Configuration for RAM-optimized rendering mode."""
    enabled: bool = False
    use_ramdisk: bool = True
    high_vram: bool = False
    chunk_long_videos: bool = False

    def get_temp_dir(self, base_dir: Path) -> Path:
        """Get appropriate temp directory based on configuration."""
        return setup_temp_directory(base_dir, self.use_ramdisk)

    def get_nvenc_args(self, codec_family: str) -> list:
        """Get NVENC args based on VRAM configuration."""
        return get_nvenc_extra_args(codec_family, self.high_vram)

    def get_hwaccel_args(self) -> list:
        """Get hardware acceleration args."""
        return get_hwaccel_input_args(self.high_vram)


# ═══════════════════════════════════════════════════════════════════════════════
# Unified Render Mode Configuration
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class RenderModeConfig:
    """Unified render mode configuration for TUI hybrid merge."""
    mode: str = "standard"  # standard, ramtest, ramdisk, high_vram
    use_ramdisk: bool = False
    high_vram: bool = False
    chunk_long_videos: bool = False
    enable_memory_tracking: bool = False
    enable_rate_limiting: bool = True

    # GPU config
    gpu_surfaces: int = 64
    gpu_extra_frames: int = 8
    gpu_lookahead: int = 32
    gpu_decode_surfaces: int = 16


def get_render_config(mode: str = "standard") -> RenderModeConfig:
    """Factory function for render mode configs.

    Args:
        mode: Render mode - "standard", "ramtest", "ramdisk", "high_vram"

    Returns:
        RenderModeConfig instance with mode-specific settings
    """
    configs = {
        "standard": RenderModeConfig(mode="standard"),
        "ramtest": RenderModeConfig(
            mode="ramtest",
            use_ramdisk=True,
            high_vram=True,
            chunk_long_videos=True,
            enable_memory_tracking=True
        ),
        "ramdisk": RenderModeConfig(
            mode="ramdisk",
            use_ramdisk=True
        ),
        "high_vram": RenderModeConfig(
            mode="high_vram",
            high_vram=True,
            gpu_surfaces=128,
            gpu_extra_frames=16,
            gpu_lookahead=48
        )
    }
    return configs.get(mode, configs["standard"])
