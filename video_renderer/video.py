#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video processing: encoding, normalization, and concatenation.

OPTIMIZED VERSION:
- Enhanced GPU utilization with proper hardware acceleration options
- Memory-efficient processing with streaming operations
- Intelligent codec compatibility checking
- Improved parallel processing with better thread management
- Automatic quality-preserving optimizations
"""

import shutil
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional, Callable, Tuple, Dict, Set
import subprocess

from .config import (
    RenderConfig,
    CodecConfig,
    ColorConfig,
    COLOR_BT709,
    DEFAULT_WIDTH,
    DEFAULT_HEIGHT,
    get_nvenc_extra_args,
    get_hwaccel_input_args,
    ALLOWED_FPS,
)
from .ffmpeg import FFmpegRunner, FFmpegProgress, probe_video, get_duration, write_concat_list

# ═══════════════════════════════════════════════════════════════════════════════
# Video Encoder
# ═══════════════════════════════════════════════════════════════════════════════


class VideoEncoder:
    """
    OPTIMIZED video encoder with:
    - Intelligent hardware acceleration selection
    - Memory-efficient processing
    - Quality-preserving optimizations
    - Fast compatibility checks with caching
    """

    # Class-level cache for compatibility checks
    _compatibility_cache: Dict[Tuple[str, str, int, int, int], bool] = {}

    def __init__(
        self,
        runner: FFmpegRunner,
        codec_config: CodecConfig,
        color_config: ColorConfig = COLOR_BT709,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        ramtest_mode: bool = False,
        high_vram: bool = False,
        fps: int = 60,
    ):
        self.runner = runner
        self.codec = codec_config
        self.color = color_config
        self.width = width
        self.height = height
        self.fps = fps

        # Ramtest mode optimizations
        self.ramtest_mode = ramtest_mode
        self.high_vram = high_vram

        # Determine acceleration type from encoder name
        self._accel_type = self._detect_acceleration_type()
        self._use_gpu = self._accel_type != "none"

    def _detect_acceleration_type(self) -> str:
        """Detect hardware acceleration type from encoder name."""
        enc = self.codec.encoder.lower()
        if "nvenc" in enc:
            return "nvenc"
        elif "qsv" in enc:
            return "qsv"
        elif "vaapi" in enc:
            return "vaapi"
        elif "videotoolbox" in enc:
            return "videotoolbox"
        return "none"

    def _detect_vaapi_device(self) -> Optional[str]:
        """
        Detect available VAAPI device on Linux systems.

        Returns:
            Device path (e.g., '/dev/dri/renderD128') or None if not found
        """
        import sys
        import platform

        # Only attempt VAAPI on Linux
        if sys.platform != "linux" and platform.system() != "Linux":
            return None

        # Common VAAPI device paths in order of preference
        possible_devices = [
            "/dev/dri/renderD128",  # Most common
            "/dev/dri/renderD129",
            "/dev/dri/renderD130",
            "/dev/dri/card0",
            "/dev/dri/card1",
        ]

        for device in possible_devices:
            try:
                if Path(device).exists() and Path(device).is_char_device():
                    return device
            except (OSError, PermissionError):
                continue

        return None

    def _parse_fps(self, fps_str: str) -> float:
        """Parse fps string (e.g., '60/1', '30000/1001') to float."""
        try:
            if "/" in fps_str:
                num, den = map(float, fps_str.split("/"))
                return num / den if den != 0 else 0.0
            return float(fps_str)
        except ValueError:
            return 0.0

    def _get_expected_codec_name(self) -> str:
        """
        Map encoder config to expected ffprobe codec name.

        Comprehensive mapping for common video codecs.
        Returns 'unknown' only for truly unrecognized codecs.
        """
        enc = self.codec.encoder.lower()

        # Modern codecs
        if "av1" in enc:
            return "av1"

        # H.264 variants
        if "h264" in enc or "x264" in enc:
            return "h264"

        # H.265/HEVC variants
        if "hevc" in enc or "x265" in enc or "h265" in enc:
            return "hevc"

        # VPx series
        if "vp9" in enc:
            return "vp9"
        if "vp8" in enc:
            return "vp8"

        # MPEG variants
        if "mpeg2" in enc or "mpeg2video" in enc:
            return "mpeg2video"
        if "mpeg4" in enc:
            return "mpeg4"

        # ProRes family
        if "prores" in enc:
            if "proxy" in enc:
                return "prores"
            if "lt" in enc:
                return "prores"
            if "hq" in enc:
                return "prores"
            if "4444" in enc:
                return "prores"
            return "prores"

        # Other common codecs
        if "mjpeg" in enc:
            return "mjpeg"
        if "wmv" in enc:
            return "wmv3"
        if "divx" in enc:
            return "mpeg4"

        # Log for unknown codecs (helps identify missing mappings)
        import logging

        logging.getLogger(__name__).warning(f"Unknown codec encoder: {self.codec.encoder}")

        return "unknown"

    def check_compatibility(self, source: Path, use_cache: bool = True) -> Tuple[bool, str]:
        """
        OPTIMIZED: Check if source video is compatible with target settings.

        Features:
        - Caching for repeated checks on same file
        - Fast-path for common formats
        - Detailed error messages
        - Early return on first incompatibility (fix: prevent result overwrite)

        Returns:
            Tuple of (is_compatible, reason)
        """
        # Create cache key
        cache_key = (str(source), self.codec.encoder, self.width, self.height, self.fps)

        if use_cache and cache_key in self._compatibility_cache:
            is_compat = self._compatibility_cache[cache_key]
            return is_compat, "Cached: Uyumlu" if is_compat else "Cached: Uyumlu degil"

        try:
            info = probe_video(source)

            # 1. Resolution - return immediately if incompatible
            if info.width != self.width or info.height != self.height:
                return (
                    False,
                    f"Cozunurluk farkli: {info.width}x{info.height} -> {self.width}x{self.height}",
                )

            # 2. Codec - return immediately if incompatible
            expected_codec = self._get_expected_codec_name()
            if info.codec.lower() != expected_codec:
                return False, f"Codec farkli: {info.codec} -> {expected_codec}"

            # 3. FPS - check against ALLOWED_FPS set for compatibility
            # 59.94 and 60.0 are considered compatible (both in ALLOWED_FPS)
            from fractions import Fraction

            source_fps = self._parse_fps(info.fps)
            source_fps_fraction = Fraction(int(source_fps * 1000), 1000).limit_denominator(1001)

            # Check if source FPS is in allowed set or matches target
            if source_fps_fraction not in ALLOWED_FPS and abs(source_fps - self.fps) > 0.1:
                return (
                    False,
                    f"FPS farkli: {float(source_fps):.2f} -> {self.fps} (izin verilen: {', '.join(str(float(f)) for f in ALLOWED_FPS)})",
                )

            # 4. Pixel Format - return immediately if incompatible
            valid_pix_fmts = {"yuv420p", "yuvj420p"}
            if expected_codec in ("hevc", "av1"):
                valid_pix_fmts.update({"yuv420p10le", "yuv420p10"})

            if info.pix_fmt not in valid_pix_fmts:
                return False, f"Pixel format uygun degil: {info.pix_fmt}"

            # All checks passed - cache and return
            if use_cache:
                self._compatibility_cache[cache_key] = True
            return True, "Uyumlu"

        except Exception as e:
            # Cache failure to avoid re-probing bad files
            if use_cache:
                self._compatibility_cache[cache_key] = False
            return False, f"Analiz hatasi: {e}"

    def is_compatible(self, source: Path) -> bool:
        """Legacy wrapper for check_compatibility."""
        ok, _ = self.check_compatibility(source)
        return ok

    def _get_optimal_threads(self) -> int:
        """
        Calculate optimal thread count for encoding.

        OPTIMIZED: Better CPU utilization while avoiding oversubscription.
        """
        import os

        cpu_count = os.cpu_count() or 4

        if self._use_gpu:
            # GPU encoding benefits from fewer threads
            return min(4, cpu_count)
        else:
            # CPU encoding can use more threads
            # Use 75% of available threads to avoid system overload
            return max(1, int(cpu_count * 0.75))

    def normalize_video(
        self,
        source: Path,
        output: Path,
        progress_callback: Optional[Callable[[FFmpegProgress], None]] = None,
        scale_algo: str = "lanczos",
    ) -> Path:
        """
        OPTIMIZED: Normalize a video to target specs.

        Improvements:
        - Smart hardware acceleration selection
        - Memory-efficient processing with streaming
        - Optimized thread count
        - Better GPU utilization

        Args:
            source: Source video path
            output: Output video path
            progress_callback: Optional progress callback
            scale_algo: Scaling algorithm (lanczos, bicubic, bilinear)

        Returns:
            Path to normalized video
        """
        if progress_callback:
            duration = get_duration(source)
            self.runner.set_total_duration(duration)
            self.runner.set_progress_callback(progress_callback)

        # Check compatibility (with caching)
        is_compat, reason = self.check_compatibility(source)

        if is_compat:
            try:
                # Fast path: direct copy without re-encoding
                print(f"  [Direct Copy] {source.name} uyumlu. Skipping encode.")
                shutil.copy2(source, output)
                if progress_callback:
                    p = FFmpegProgress(
                        percent=100.0,
                        time_seconds=duration,
                        fps=float(self.fps),
                        speed=float("inf"),
                    )
                    progress_callback(p)
                return output
            except Exception as e:
                print(f"  [WARN] Direct copy failed: {e}. Falling back to re-encoding...")

        print(f"  [Re-encode] {source.name}: {reason}")

        # Build optimized FFmpeg command
        cmd = self._build_normalize_command(source, output, scale_algo)

        gpu_error = None
        try:
            self.runner.run(cmd, capture_progress=bool(progress_callback))
        except Exception as e:
            # Fallback to software encoding if hardware fails
            if self._use_gpu:
                gpu_error = e
                print(f"  [WARN] Hardware encoding failed: {e}. Falling back to software...")
                try:
                    cmd_software = self._build_normalize_command(
                        source, output, scale_algo, force_software=True
                    )
                    self.runner.run(cmd_software, capture_progress=bool(progress_callback))
                except Exception as sw_error:
                    # Both GPU and software encoding failed
                    raise RuntimeError(
                        f"Failed to encode video after attempting both GPU and software encoding.\n\n"
                        f"GPU Error: {gpu_error}\n"
                        f"Software Error: {sw_error}\n\n"
                        f"Suggestions:\n"
                        f"- Try a different codec (h264 instead of av1/hevc)\n"
                        f"- Lower resolution (1280x720 instead of 1920x1080)\n"
                        f"- Update GPU drivers\n"
                        f"- Check available disk space\n"
                        f"- Verify source file is not corrupted"
                    ) from sw_error
            else:
                raise

        return output

    def _build_normalize_command(
        self, source: Path, output: Path, scale_algo: str, force_software: bool = False
    ) -> List[str]:
        """Build optimized FFmpeg command for video normalization.

        OPTIMIZED: Added performance flags for better encoding speed and web optimization.

        Includes ramtest mode optimizations for high-VRAM systems.
        """
        cmd = ["ffmpeg", "-y"]

        # Hardware acceleration options
        if self._use_gpu and not force_software:
            if self._accel_type == "nvenc":
                # NVIDIA NVENC optimizations
                # Apply ramtest high-VRAM settings if enabled
                if self.high_vram:
                    cmd.extend(get_hwaccel_input_args(high_vram=True))
                else:
                    cmd.extend(["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"])
            elif self._accel_type == "qsv":
                # Intel QSV optimizations
                cmd.extend(["-hwaccel", "qsv", "-hwaccel_output_format", "qsv"])
            elif self._accel_type == "vaapi":
                # VAAPI (Linux AMD/Intel) optimizations with dynamic device detection
                vaapi_device = self._detect_vaapi_device()
                if vaapi_device:
                    cmd.extend(
                        [
                            "-hwaccel",
                            "vaapi",
                            "-hwaccel_output_format",
                            "vaapi",
                            "-vaapi_device",
                            vaapi_device,
                        ]
                    )
                else:
                    # No VAAPI device found, skip hardware acceleration
                    import logging

                    logging.getLogger(__name__).warning(
                        "No VAAPI device found, falling back to software encoding"
                    )
                    # Force software encoding by setting acceleration to none
                    self._use_gpu = False
                    self._accel_type = "none"

        # Input file
        cmd.extend(["-i", str(source)])

        # Build filter chain based on acceleration type
        if self._use_gpu and not force_software:
            filter_complex = self._build_gpu_filter(scale_algo)
        else:
            filter_complex = self._build_cpu_filter(scale_algo)

        cmd.extend(["-vf", filter_complex])

        # FPS
        cmd.extend(["-r", str(self.fps)])

        # Thread optimization
        cmd.extend(["-threads", str(self._get_optimal_threads())])

        # Codec-specific args
        codec_args = self.codec.to_ffmpeg_args()

        # Apply ramtest NVENC optimizations if enabled
        if self.high_vram and "nvenc" in self.codec.encoder.lower():
            # Determine codec family
            codec_family = (
                "av1"
                if "av1" in self.codec.encoder.lower()
                else "h265" if "hevc" in self.codec.encoder.lower() else "h264"
            )
            nvenc_args = get_nvenc_extra_args(codec_family, high_vram=True)
            # Override default args with optimized ones
            codec_args = nvenc_args

        cmd.extend(codec_args)

        # Color space
        cmd.extend(self.color.to_ffmpeg_args())

        # Performance optimizations
        cmd.extend(
            [
                "-tune",
                "fastdecode",  # Optimize for faster decoding
            ]
        )

        # No audio (video only)
        cmd.extend(["-an", str(output)])

        return cmd

    def _build_gpu_filter(self, scale_algo: str) -> str:
        """Build GPU-accelerated filter chain."""
        if self._accel_type == "nvenc":
            # NVIDIA CUDA scaling
            return (
                f"scale_cuda={self.width}:{self.height}:"
                f"interp_algo={scale_algo}:"
                f"force_original_aspect_ratio=decrease,"
                f"pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2,"
                f"setsar=1"
            )
        elif self._accel_type == "qsv":
            # Intel QSV scaling
            return (
                f"vpp_qsv=w={self.width}:h={self.height}:"
                f"interp_algo={scale_algo}:"
                f"force_original_aspect_ratio=decrease,"
                f"pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2"
            )
        elif self._accel_type == "vaapi":
            # VAAPI scaling
            return (
                f"scale_vaapi=w={self.width}:h={self.height}:"
                f"force_original_aspect_ratio=decrease,"
                f"pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2"
            )
        else:
            # Fallback to CPU
            return self._build_cpu_filter(scale_algo)

    def _build_cpu_filter(self, scale_algo: str) -> str:
        """Build CPU-optimized filter chain."""
        return (
            f"scale={self.width}:{self.height}:"
            f"flags={scale_algo}:"
            f"force_original_aspect_ratio=decrease,"
            f"pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2,"
            f"format=yuv420p"
        )

    def concat_videos(
        self,
        intro: Path,
        loop: Path,
        total_seconds: int,
        tmp_dir: Path,
        progress_callback: Optional[Callable[[FFmpegProgress], None]] = None,
    ) -> Path:
        """
        Concatenate intro + repeated loop to reach target duration.
        Uses stream copy for speed (no re-encoding).

        Args:
            intro: Normalized intro video
            loop: Normalized loop video
            total_seconds: Target duration in seconds
            tmp_dir: Temp directory for concat list
            progress_callback: Optional progress callback

        Returns:
            Path to concatenated video
        """
        intro_duration = get_duration(intro)
        loop_duration = get_duration(loop)

        remaining = max(0.0, total_seconds - intro_duration)
        loop_count = int(math.ceil(remaining / loop_duration)) if loop_duration > 0 else 0

        # Write concat list
        concat_list = tmp_dir / "video_list.txt"
        files = [intro] + [loop] * loop_count
        write_concat_list(files, concat_list)

        output = tmp_dir / "video_only.mp4"

        if progress_callback:
            self.runner.set_total_duration(total_seconds)
            self.runner.set_progress_callback(progress_callback)

        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list),
            "-c:v",
            "copy",
            "-t",
            str(total_seconds),  # Trim to exact duration
            "-movflags",
            "+faststart",
            str(output),
        ]

        self.runner.run(cmd, capture_progress=bool(progress_callback))
        return output


# ═══════════════════════════════════════════════════════════════════════════════
# Parallel Encoding
# ═══════════════════════════════════════════════════════════════════════════════


def encode_parallel(
    encoder: VideoEncoder,
    sources: List[Tuple[Path, Path]],  # List of (source, output) pairs
    progress_callback: Optional[Callable[[str, FFmpegProgress], None]] = None,
) -> List[Path]:
    """
    Encode multiple videos in parallel.

    Args:
        encoder: VideoEncoder instance
        sources: List of (source_path, output_path) tuples
        progress_callback: Callback receiving (label, progress)

    Returns:
        List of output paths
    """
    results = []

    def encode_one(source: Path, output: Path, label: str) -> Path:
        def wrapped_callback(p: FFmpegProgress):
            if progress_callback:
                progress_callback(label, p)

        return encoder.normalize_video(source, output, wrapped_callback)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {}
        for i, (src, out) in enumerate(sources):
            label = f"Encoding {src.name}"
            future = executor.submit(encode_one, src, out, label)
            futures[future] = out

        for future in as_completed(futures):
            output = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                raise RuntimeError(f"Encoding failed for {output.name}: {e}") from e

    return results
