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
from .validator import PostRenderValidator

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
            # GPU pipeline still needs enough CPU threads for decode/filter/feed.
            return min(8, cpu_count)
        else:
            # CPU encoding can use more threads
            # Keep one core free for OS responsiveness.
            return max(1, cpu_count - 1)

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
            # Fixed: Preserve original exception context with 'raise from'
            # Fallback to software encoding if hardware fails
            if self._use_gpu:
                gpu_error = e
                import logging
                logging.getLogger(__name__).warning(f"Hardware encoding failed: {e}. Falling back to software...")
                print(f"  [WARN] Hardware encoding failed: {e}. Falling back to software...")
                try:
                    cmd_software = self._build_normalize_command(
                        source, output, scale_algo, force_software=True
                    )
                    self.runner.run(cmd_software, capture_progress=bool(progress_callback))
                except Exception as sw_error:
                    # Fixed: Use exception chaining to preserve both error contexts
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
                    ) from sw_error  # Preserves software error context
            else:
                # Fixed: Re-raise with original context preserved
                raise  # 'raise' without arguments preserves the original traceback

        # Verify output file was created and is valid
        if not output.exists():
            raise RuntimeError(f"Normalize failed: output file not created at {output}")

        output_duration = get_duration(output)
        source_duration = get_duration(source)

        # Check if output duration is reasonable (within 10% of source)
        if source_duration > 0:
            duration_diff = abs(output_duration - source_duration) / source_duration
            if duration_diff > 0.1:  # More than 10% difference
                import logging
                logging.getLogger(__name__).warning(
                    f"Normalize output duration differs significantly from source: "
                    f"source={source_duration:.1f}s, output={output_duration:.1f}s "
                    f"({duration_diff*100:.1f}% difference)"
                )

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
                "-movflags",
                "+faststart",
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

    def _get_fast_concat_codec_args(self) -> List[str]:
        """
        Get fastest possible codec args for the concat re-encode step.

        Since input videos are already at target quality (normalized),
        this step only needs to fix timestamps. Use fastest preset
        to minimize re-encode time while maintaining codec compatibility.
        """
        enc = self.codec.encoder.lower()

        # NVIDIA NVENC — already very fast, use p1 (fastest) preset
        if "nvenc" in enc:
            args = ["-c:v", self.codec.encoder, "-preset", "p1"]
            # Use VBR with quality target
            cq = self.codec.crf
            args.extend(["-rc", "vbr", "-cq", str(cq), "-b:v", "0"])
            if self.codec.profile:
                args.extend(["-profile:v", self.codec.profile])
            # Minimal lookahead for speed
            args.extend(["-rc-lookahead", "8", "-surfaces", "64"])
            if "hevc" in enc:
                args.extend(["-tag:v", "hvc1"])
            return args

        # Intel QSV — use veryfast preset
        if "qsv" in enc:
            args = ["-c:v", self.codec.encoder, "-preset", "veryfast"]
            args.extend(["-global_quality", str(self.codec.crf)])
            if self.codec.profile:
                args.extend(["-profile:v", self.codec.profile])
            if "hevc" in enc:
                args.extend(["-tag:v", "hvc1"])
            return args

        # VAAPI — use QP mode (no preset concept)
        if "vaapi" in enc:
            args = ["-c:v", self.codec.encoder, "-qp", str(self.codec.crf)]
            if self.codec.profile:
                args.extend(["-profile:v", self.codec.profile])
            if "hevc" in enc:
                args.extend(["-tag:v", "hvc1"])
            return args

        # Software: libsvtav1 — preset 12 is fastest
        if "svtav1" in enc or "svt-av1" in enc:
            return ["-c:v", "libsvtav1", "-preset", "12", "-crf", str(self.codec.crf)]

        # Software: libx265 — ultrafast
        if "x265" in enc or "libx265" in enc:
            return [
                "-c:v", "libx265", "-preset", "ultrafast",
                "-crf", str(self.codec.crf), "-tag:v", "hvc1",
            ]

        # Software: libx264 — ultrafast (default fallback)
        if "x264" in enc or "libx264" in enc:
            return [
                "-c:v", "libx264", "-preset", "ultrafast",
                "-crf", str(self.codec.crf),
            ]

        # Unknown encoder: use same codec args but log warning
        import logging
        logging.getLogger(__name__).warning(
            f"Unknown encoder '{self.codec.encoder}' for fast concat, using default args"
        )
        return self.codec.to_ffmpeg_args()

    def _get_bsf_for_codec(self) -> Optional[str]:
        """Get the bitstream filter needed to remux MP4 → MPEG-TS for this codec."""
        enc = self.codec.encoder.lower()
        if "h264" in enc or "x264" in enc:
            return "h264_mp4toannexb"
        if "hevc" in enc or "x265" in enc or "h265" in enc:
            return "hevc_mp4toannexb"
        # AV1, VP9 etc. do not need a bitstream filter for TS remux
        return None

    def _remux_to_ts(self, mp4_path: Path, ts_path: Path) -> None:
        """Remux an MP4 file to MPEG-TS format (stream copy, no re-encode)."""
        cmd = [
            "ffmpeg", "-y",
            "-i", str(mp4_path),
            "-c:v", "copy",
            "-an",
        ]
        bsf = self._get_bsf_for_codec()
        if bsf:
            cmd.extend(["-bsf:v", bsf])
        cmd.extend(["-f", "mpegts", str(ts_path)])
        self.runner.run_simple(cmd)

    def concat_videos(
        self,
        intro: Path,
        loop: Path,
        total_seconds: int,
        tmp_dir: Path,
        progress_callback: Optional[Callable[[FFmpegProgress], None]] = None,
        on_duration_error: Optional[Callable[[float, float], bool]] = None,
    ) -> Path:
        """
        Concatenate intro + repeated loop to reach target duration.

        Strategy (all stream copy, no re-encoding, frame-exact duration):
          1. Primary: TS intermediate concat
             - Remux MP4 → MPEG-TS (fixes timestamp continuity)
             - Concat demuxer on TS files → MP4 with -vframes (frame-exact)
          2. Fallback: Two-pass MP4 concat
             - Raw concat with -c:v copy (has all frames)
             - Remux with -r FPS + -vframes (frame-exact, timestamp fix)
          3. Last resort: Re-encode with fastest settings
          
        Args:
            on_duration_error: Optional callback(actual_duration, target_duration) → bool
                              Called if duration is wrong, returns True if user wants to fix it
        """
        import logging
        logger = logging.getLogger(__name__)

        intro_duration = get_duration(intro)
        loop_duration = get_duration(loop)

        remaining = max(0.0, total_seconds - intro_duration)
        loop_count = int(math.ceil(remaining / loop_duration)) if loop_duration > 0 else 0

        output = tmp_dir / "video_only.mp4"
        target_frames = int(total_seconds * self.fps)

        # ── Strategy 1: TS intermediate concat (best for AV1/H264/H265) ──
        try:
            intro_ts = tmp_dir / "intro_concat.ts"
            loop_ts = tmp_dir / "loop_concat.ts"

            # Remux MP4 → MPEG-TS (stream copy, instant)
            if not intro_ts.exists():
                print(f"  [TS Remux] intro -> .ts")
                self._remux_to_ts(intro, intro_ts)
            if not loop_ts.exists():
                print(f"  [TS Remux] loop -> .ts")
                self._remux_to_ts(loop, loop_ts)

            # Concat demuxer on TS files → MP4 (frame-exact via -vframes)
            concat_list_ts = tmp_dir / "video_list_ts.txt"
            ts_files = [intro_ts] + [loop_ts] * loop_count
            write_concat_list(ts_files, concat_list_ts)

            print(f"  [Concat] 1 intro + {loop_count} loop (TS stream copy)")
            cmd = [
                "ffmpeg", "-y",
                "-r", str(self.fps),  # Reset FPS for proper frame counting
                "-f", "concat", "-safe", "0",
                "-i", str(concat_list_ts),
                "-c:v", "copy", "-an",
                "-fps_mode", "cfr",  # Constant frame rate
                "-vframes", str(target_frames),  # Frame-exact (1728000 @ 60fps for 8h)
                "-movflags", "+faststart",
                str(output),
            ]
            self.runner.run(cmd, capture_progress=False)

            # Verify output exists
            if output.exists():
                output_duration = get_duration(output)
                tolerance = max(5.0, total_seconds * 0.02)
                if output_duration > 10 and abs(output_duration - total_seconds) <= tolerance:
                    print(f"  [OK] video_only.mp4: {output_duration:.1f}s (TS concat)")
                    # Cleanup TS intermediates
                    for f in [intro_ts, loop_ts, concat_list_ts]:
                        if f.exists():
                            f.unlink()
                    return output
                else:
                    raise RuntimeError(
                        f"TS concat duration wrong: {output_duration:.1f}s vs target {total_seconds}s"
                    )

            raise RuntimeError("TS concat output not created")

        except Exception as ts_err:
            logger.warning(f"TS concat failed: {ts_err}")
            print(f"  [WARN] TS concat basarisiz: {ts_err}")
            # Cleanup
            for f in [tmp_dir / "intro_concat.ts", tmp_dir / "loop_concat.ts",
                       tmp_dir / "video_list_ts.txt"]:
                if f.exists():
                    f.unlink()
            if output.exists():
                output.unlink()

        # ── Strategy 2: Two-pass MP4 concat + timestamp fix (frame-exact) ──
        try:
            raw_output = tmp_dir / "video_only_raw.mp4"
            concat_list = tmp_dir / "video_list.txt"
            files = [intro] + [loop] * loop_count
            write_concat_list(files, concat_list)

            # Pass 1: Raw concat (all frames, possibly broken timestamps)
            print(f"  [Concat Pass 1] raw MP4 concat (stream copy)")
            cmd_raw = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(concat_list),
                "-c:v", "copy", "-an",
                str(raw_output),
            ]
            self.runner.run(cmd_raw, capture_progress=False)

            if not raw_output.exists():
                raise RuntimeError("Raw concat output not created")

            # Pass 2: Fix timestamps via remux with forced framerate + frame-exact trim
            # -r as INPUT option forces timestamp recalculation from frame count
            print(f"  [Concat Pass 2] timestamp fix remux (-r {self.fps}, -vframes {target_frames})")
            cmd_fix = [
                "ffmpeg", "-y",
                "-r", str(self.fps),
                "-fflags", "+genpts",
                "-i", str(raw_output),
                "-c:v", "copy", "-an",
                "-vframes", str(target_frames),  # Frame-exact trim
                "-movflags", "+faststart",
                str(output),
            ]
            self.runner.run(cmd_fix, capture_progress=False)

            # Cleanup raw
            if raw_output.exists():
                raw_output.unlink()

            # Verify
            if output.exists():
                output_duration = get_duration(output)
                tolerance = max(5.0, total_seconds * 0.02)
                if output_duration > 10 and abs(output_duration - total_seconds) <= tolerance:
                    print(f"  [OK] video_only.mp4: {output_duration:.1f}s (2-pass fix)")
                    return output
                else:
                    raise RuntimeError(
                        f"2-pass concat duration wrong: {output_duration:.1f}s vs target {total_seconds}s"
                    )

            raise RuntimeError("2-pass concat output not created")

        except Exception as fix_err:
            logger.warning(f"2-pass concat failed: {fix_err}")
            print(f"  [WARN] 2-pass concat basarisiz: {fix_err}")
            for f in [tmp_dir / "video_only_raw.mp4", tmp_dir / "video_list.txt"]:
                if f.exists():
                    f.unlink()
            if output.exists():
                output.unlink()

        # ── Strategy 3: Re-encode with fastest settings (last resort) ──
        print(f"  [WARN] Re-encode fallback kullaniliyor...")
        concat_list = tmp_dir / "video_list.txt"
        files = [intro] + [loop] * loop_count
        write_concat_list(files, concat_list)

        cmd = ["ffmpeg", "-y"]
        if self._use_gpu and self._accel_type == "nvenc":
            cmd.extend(["-hwaccel", "cuda"])
        cmd.extend([
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-an", "-fps_mode", "cfr", "-r", str(self.fps),
        ])
        cmd.extend(self._get_fast_concat_codec_args())
        cmd.extend(self.color.to_ffmpeg_args())
        cmd.extend([
            "-vframes", str(target_frames),  # Frame-exact
            "-movflags", "+faststart",
            str(output),
        ])
        self.runner.run(cmd, capture_progress=False)

        if not output.exists():
            raise RuntimeError(f"Concat failed: output file not created at {output}")

        output_duration = get_duration(output)
        if output_duration < 10:
            raise RuntimeError(f"Concat output too short: {output_duration:.1f}s")

        print(f"  [OK] video_only.mp4: {output_duration:.1f}s (re-encode fallback)")
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


# ═══════════════════════════════════════════════════════════════════════════════
# Validation Integration
# ═══════════════════════════════════════════════════════════════════════════════


def validate_rendered_output(
    output_path: Path,
    target_duration: int,
    target_specs: dict,
) -> bool:
    """
    Validate rendered output video after muxing.

    This is a convenience function for post-render validation that can be called
    after the final mux step to verify the output meets specifications.

    Args:
        output_path: Path to the rendered output video
        target_duration: Target duration in seconds
        target_specs: Dictionary with expected video specs:
            - codec: Expected codec name
            - width: Expected width
            - height: Expected height
            - fps: Expected FPS
            - has_audio: Whether audio should be present (default: True)

    Returns:
        True if validation passes, False otherwise

    Raises:
        RuntimeError: If validation fails with critical errors
    """
    validator = PostRenderValidator()

    result = validator.validate_output(
        output_path=output_path,
        target_duration=target_duration,
        target_specs=target_specs
    )

    # Log validation results
    if result.valid:
        print(f"  [Validation] ✓ Output validation passed")
        if result.warnings:
            print(f"  [Validation] ⚠ {len(result.warnings)} warnings:")
            for warning in result.warnings:
                print(f"    - {warning.message}")
    else:
        print(f"  [Validation] ✗ Output validation failed with {len(result.errors)} errors")
        for error in result.errors:
            print(f"    - {error.message}")
            if error.details:
                print(f"      Details: {error.details}")
            if error.suggestion:
                print(f"      Suggestion: {error.suggestion}")

    # Return validation status
    return result.valid
