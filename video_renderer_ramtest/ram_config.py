#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAM/VRAM Optimized Configuration for High-Memory Systems.

This version uses:
- tmpfs (/dev/shm) for temp files when available (Linux)
- Larger GPU buffers for VRAM utilization
- Chunked processing for very long videos (optional)
"""

import os
import shutil
from pathlib import Path

# RAM Disk Configuration
# On Linux, /dev/shm is a tmpfs mount (RAM-based)
# Typical size is half of RAM

def get_ramdisk_path() -> Path:
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


def setup_temp_directory(base_dir: Path) -> Path:
    """
    Setup temp directory, preferring RAM disk if available.
    
    Args:
        base_dir: Project base directory (fallback location)
        
    Returns:
        Path to temp directory
    """
    # Try RAM disk first
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


# GPU Buffer Configuration
# These values are tuned for 20GB VRAM
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


def get_nvenc_extra_args(codec_family: str = "av1") -> list:
    """
    Get optimized NVENC arguments for high-VRAM systems.
    
    Args:
        codec_family: "av1", "h264", or "h265"
        
    Returns:
        List of FFmpeg arguments
    """
    base_args = [
        "-rc", "vbr",
        "-spatial_aq", "1",
        "-b_ref_mode", "0",
        "-rc-lookahead", str(GPU_CONFIG["rc_lookahead"]),
        "-surfaces", str(GPU_CONFIG["surfaces"]),
        "-extra_hw_frames", str(GPU_CONFIG["extra_hw_frames"]),
    ]
    
    if codec_family == "av1":
        base_args.extend(["-cq", "30", "-b:v", "0"])
    elif codec_family == "h265":
        base_args.extend(["-cq", "26", "-b:v", "0", "-tag:v", "hvc1"])
    else:  # h264
        base_args.extend(["-cq", "23", "-b:v", "0"])
    
    return base_args


def get_hwaccel_input_args() -> list:
    """Get hardware acceleration input arguments for decoding."""
    return [
        "-hwaccel", "cuda",
        "-hwaccel_output_format", "cuda",
        "-extra_hw_frames", str(GPU_CONFIG["decode_surfaces"]),
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


if __name__ == "__main__":
    # Test configuration
    print("RAM Disk:", get_ramdisk_path())
    print("GPU Config:", GPU_CONFIG)
    print("NVENC Args (AV1):", get_nvenc_extra_args("av1"))
