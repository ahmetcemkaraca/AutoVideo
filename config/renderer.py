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
from typing import Any, Set, Dict, List, Optional

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


def check_nvenc_readiness() -> Dict[str, Any]:
    """
    Comprehensive NVENC readiness check.
    Verifies GPU driver, CUDA, and FFmpeg NVENC support.

    Returns:
        Dict with check results:
        {
            "ready": bool,           # Overall NVENC readiness
            "gpu_found": bool,       # nvidia-smi detects a GPU
            "gpu_name": str,         # GPU model name
            "driver_version": str,   # NVIDIA driver version
            "cuda_version": str,     # CUDA compute capability
            "vram_total_mb": int,    # Total VRAM in MB
            "vram_free_mb": int,     # Free VRAM in MB
            "ffmpeg_nvenc": bool,    # FFmpeg has NVENC encoders listed
            "encoders_working": dict,# {encoder: bool} actual test results
            "issues": list,          # List of issue descriptions
        }
    """
    result: Dict[str, Any] = {
        "ready": False,
        "gpu_found": False,
        "gpu_name": "",
        "driver_version": "",
        "cuda_version": "",
        "vram_total_mb": 0,
        "vram_free_mb": 0,
        "ffmpeg_nvenc": False,
        "encoders_working": {},
        "issues": [],
    }

    # 1. Check nvidia-smi availability and GPU presence
    try:
        smi = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,driver_version,memory.total,memory.free",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True, text=True, timeout=5,
        )
        if smi.returncode == 0 and smi.stdout.strip():
            parts = [p.strip() for p in smi.stdout.strip().split("\n")[0].split(",")]
            if len(parts) >= 4:
                result["gpu_found"] = True
                result["gpu_name"] = parts[0]
                result["driver_version"] = parts[1]
                result["vram_total_mb"] = int(float(parts[2]))
                result["vram_free_mb"] = int(float(parts[3]))
            else:
                result["issues"].append("nvidia-smi ciktisi beklenmeyen formatta")
        else:
            result["issues"].append(
                "nvidia-smi calistirilamadi veya GPU bulunamadi. "
                "NVIDIA driver kurulu mu? https://www.nvidia.com/drivers"
            )
    except FileNotFoundError:
        result["issues"].append(
            "nvidia-smi bulunamadi. NVIDIA driver kurulu degil. "
            "https://www.nvidia.com/drivers adresinden indirin."
        )
    except subprocess.TimeoutExpired:
        result["issues"].append("nvidia-smi zaman asimina ugradi. GPU takili/donmus olabilir.")
    except Exception as e:
        result["issues"].append(f"nvidia-smi hatasi: {e}")

    # 2. Check CUDA compute capability
    if result["gpu_found"]:
        try:
            cuda_check = subprocess.run(
                ["nvidia-smi", "--query-gpu=compute_cap", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=5,
            )
            if cuda_check.returncode == 0:
                compute_cap = cuda_check.stdout.strip().split("\n")[0].strip()
                result["cuda_version"] = compute_cap
                try:
                    major = int(compute_cap.split(".")[0])
                    if major < 3:
                        result["issues"].append(
                            f"GPU compute capability {compute_cap} < 3.0. "
                            f"NVENC icin en az 3.0 gerekli (Kepler veya ustu)."
                        )
                except (ValueError, IndexError):
                    pass
        except Exception:
            pass

    # 3. Check FFmpeg NVENC encoder support
    try:
        enc_check = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=10,
        )
        if enc_check.returncode == 0:
            output = enc_check.stdout
            nvenc_encoders = ["h264_nvenc", "hevc_nvenc", "av1_nvenc"]
            found_any = any(enc in output for enc in nvenc_encoders)
            result["ffmpeg_nvenc"] = found_any
            if not found_any:
                result["issues"].append(
                    "FFmpeg'de NVENC encoder bulunamadi. "
                    "FFmpeg NVENC destegi ile derlenmis olmali. "
                    "Windows: gyan.dev/ffmpeg/builds/ adresinden full build indirin. "
                    "Linux: sudo apt install ffmpeg (veya NVIDIA SDK ile derleyin)."
                )
    except FileNotFoundError:
        result["issues"].append("FFmpeg bulunamadi. Lutfen FFmpeg kurun.")
    except Exception as e:
        result["issues"].append(f"FFmpeg encoder kontrol hatasi: {e}")

    # 4. Actually test NVENC encoders
    if result["gpu_found"] and result["ffmpeg_nvenc"]:
        for encoder in ["h264_nvenc", "hevc_nvenc", "av1_nvenc"]:
            try:
                test_cmd = [
                    "ffmpeg", "-hide_banner", "-y",
                    "-f", "lavfi", "-i", "color=black:s=64x64:d=0.04",
                    "-c:v", encoder, "-t", "0.04",
                    "-f", "null", "-",
                ]
                test_result = subprocess.run(
                    test_cmd,
                    capture_output=True, text=True, timeout=10, check=False,
                )
                working = test_result.returncode == 0 and "Error" not in test_result.stderr
                result["encoders_working"][encoder] = working
                if not working:
                    err_lines = [
                        l.strip() for l in test_result.stderr.split("\n")
                        if "Error" in l or "error" in l or "Cannot" in l
                    ]
                    err_msg = err_lines[0] if err_lines else "Bilinmeyen hata"
                    result["issues"].append(f"{encoder} calismiyor: {err_msg}")
            except subprocess.TimeoutExpired:
                result["encoders_working"][encoder] = False
                result["issues"].append(f"{encoder} testi zaman asimina ugradi")
            except Exception as e:
                result["encoders_working"][encoder] = False
                result["issues"].append(f"{encoder} test hatasi: {e}")

    # 5. Overall readiness
    result["ready"] = (
        result["gpu_found"]
        and result["ffmpeg_nvenc"]
        and any(result["encoders_working"].values())
    )

    return result


def print_nvenc_status():
    """Print NVENC readiness status to console (for CLI diagnostics)."""
    status = check_nvenc_readiness()

    lines = []
    lines.append("=" * 50)
    lines.append("NVENC Durum Kontrolu")
    lines.append("=" * 50)

    if status["gpu_found"]:
        lines.append(f"  GPU     : {status['gpu_name']}")
        lines.append(f"  Driver  : {status['driver_version']}")
        lines.append(f"  Compute : {status['cuda_version']}")
        lines.append(f"  VRAM    : {status['vram_free_mb']} MB bos / {status['vram_total_mb']} MB toplam")
    else:
        lines.append("  GPU     : Bulunamadi")

    lines.append(f"  FFmpeg  : {'NVENC destekli' if status['ffmpeg_nvenc'] else 'NVENC yok'}")

    if status["encoders_working"]:
        for enc, ok in status["encoders_working"].items():
            symbol = "OK" if ok else "FAIL"
            lines.append(f"  {enc:15s}: {symbol}")

    lines.append("-" * 50)
    if status["ready"]:
        lines.append("  Sonuc: NVENC KULLANILABILIR")
    else:
        lines.append("  Sonuc: NVENC KULLANILAMIYOR")
        for issue in status["issues"]:
            lines.append(f"  ! {issue}")

    lines.append("=" * 50)
    print("\n".join(lines))

    return status["ready"]


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
