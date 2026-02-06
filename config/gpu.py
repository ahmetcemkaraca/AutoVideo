#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPU and RAM optimization configuration.

Extracted from video_renderer/config.py and video_renderer_ramtest/config.py.
Handles VRAM optimization, RAM disk setup, and render mode configurations.
"""

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List
from enum import Enum


# ═══════════════════════════════════════════════════════════════════════════════
# Profile Enum
# ═══════════════════════════════════════════════════════════════════════════════

class Profile(str, Enum):
    """GPU/RAM optimization profiles."""
    STANDARD = "standard"
    HIGH_VRAM = "high_vram"
    ULTRA = "ultra"


# ═══════════════════════════════════════════════════════════════════════════════
# GPU Buffer Configuration for high-VRAM systems
# ═══════════════════════════════════════════════════════════════════════════════

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


# Memory limits for chunked processing
CHUNK_CONFIG = {
    # Max chunk duration in seconds (2 hours)
    "max_chunk_duration": 7200,

    # Minimum RAM for chunked mode (GB)
    "min_ram_for_full": 64,

    # Enable chunked mode automatically for videos longer than this (hours)
    "auto_chunk_threshold_hours": 12,
}


# ═══════════════════════════════════════════════════════════════════════════════
# GPU Configuration Class
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class GPUConfig:
    """GPU/RAM optimization configuration."""
    profile: Profile = Profile.STANDARD

    def get_surfaces(self) -> int:
        return {
            Profile.STANDARD: 64,
            Profile.HIGH_VRAM: 128,
            Profile.ULTRA: 256
        }[self.profile]

    def get_nvenc_args(self, codec_family: str) -> List[str]:
        surfaces = self.get_surfaces()
        extra_frames = self._get_extra_frames()
        lookahead = self._get_lookahead()

        return [
            "-rc", "vbr",
            "-surfaces", str(surfaces),
            "-extra_hw_frames", str(extra_frames),
            "-rc-lookahead", str(lookahead),
        ]

    def _get_extra_frames(self) -> int:
        return {
            Profile.STANDARD: 8,
            Profile.HIGH_VRAM: 16,
            Profile.ULTRA: 32
        }[self.profile]

    def _get_lookahead(self) -> int:
        return {
            Profile.STANDARD: 32,
            Profile.HIGH_VRAM: 48,
            Profile.ULTRA: 64
        }[self.profile]


# ═══════════════════════════════════════════════════════════════════════════════
# RAM Disk Configuration
# ═══════════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════════
# GPU Configuration Classes
# ═══════════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════════
# RAM/VRAM Optimized Configuration
# ═══════════════════════════════════════════════════════════════════════════════

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
