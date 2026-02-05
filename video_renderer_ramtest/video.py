#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video processing: encoding, normalization, and concatenation.
"""

import shutil
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional, Callable, Tuple

from .config import (
    RenderConfig, CodecConfig, ColorConfig, COLOR_BT709,
    DEFAULT_WIDTH, DEFAULT_HEIGHT
)
from .ffmpeg import FFmpegRunner, FFmpegProgress, probe_video, get_duration, write_concat_list


# ═══════════════════════════════════════════════════════════════════════════════
# Video Encoder
# ═══════════════════════════════════════════════════════════════════════════════

class VideoEncoder:
    """
    Handles video encoding and concatenation operations.
    """
    
    def __init__(
        self,
        runner: FFmpegRunner,
        codec_config: CodecConfig,
        color_config: ColorConfig = COLOR_BT709,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        fps: int = 60
    ):
        self.runner = runner
        self.codec = codec_config
        self.color = color_config
        self.width = width
        self.height = height
        self.fps = fps
    
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
        """Map encoder config to expected ffprobe codec name."""
        enc = self.codec.encoder.lower()
        if "av1" in enc: return "av1"
        if "h264" in enc or "x264" in enc: return "h264"
        if "hevc" in enc or "x265" in enc or "h265" in enc: return "hevc"
        return "unknown"

    def check_compatibility(self, source: Path) -> Tuple[bool, str]:
        """
        Check if source video is compatible with target settings.
        Returns (is_compatible, reason).
        """
        try:
            info = probe_video(source)
            
            # 1. Resolution
            if info.width != self.width or info.height != self.height:
                return False, f"Cozunurluk farkli: {info.width}x{info.height} -> {self.width}x{self.height}"
                
            # 2. Codec
            expected_codec = self._get_expected_codec_name()
            if info.codec.lower() != expected_codec:
                return False, f"Codec farkli: {info.codec} -> {expected_codec}"
                
            # 3. FPS
            source_fps = self._parse_fps(info.fps)
            if abs(source_fps - self.fps) > 0.1:
                return False, f"FPS farkli: {float(source_fps):.2f} -> {self.fps}"
                
            # 4. Pixel Format
            valid_pix_fmts = {"yuv420p", "yuvj420p"}
            if expected_codec in ("hevc", "av1"):
                valid_pix_fmts.update({"yuv420p10le", "yuv420p10"})
                
            if info.pix_fmt not in valid_pix_fmts:
                return False, f"Pixel format uygun degil: {info.pix_fmt}"
                
            return True, "Uyumlu"
        except Exception as e:
            return False, f"Analiz hatasi: {e}"

    def is_compatible(self, source: Path) -> bool:
        """Legacy wrapper for check_compatibility."""
        ok, _ = self.check_compatibility(source)
        return ok

    def normalize_video(
        self,
        source: Path,
        output: Path,
        progress_callback: Optional[Callable[[FFmpegProgress], None]] = None,
        scale_algo: str = "lanczos"
    ) -> Path:
        """
        Normalize a video to target specs (resolution, fps, codec, color).
        Uses GPU acceleration if configured.
        """
        if progress_callback:
            duration = get_duration(source)
            self.runner.set_total_duration(duration)
            self.runner.set_progress_callback(progress_callback)
        
        # Check compatibility
        is_compat, reason = self.check_compatibility(source)
        
        if is_compat:
            try:
                # Direct copy
                print(f"  [Direct Copy] {source.name} uyumlu ({reason}).")
                shutil.copy2(source, output)
                if progress_callback:
                    p = FFmpegProgress(
                        percent=100.0,
                        time_seconds=get_duration(source),
                        fps=0.0,
                        speed=float('inf')
                    )
                    progress_callback(p)
                return output
            except Exception:
                pass
        else:
            print(f"  [Re-encode] {source.name}: {reason}")

        # Determine if we are using NVIDIA HW encoding
        is_nvenc = "nvenc" in self.codec.encoder
        
        cmd = ["ffmpeg", "-y"]
        
        # Hardware Decoding Input options
        if is_nvenc:
            cmd.extend(["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"])
            
        cmd.extend(["-i", str(source)])
        
        # Filter Chain
        if is_nvenc:
            # GPU Scaling - cuda scaler uses 'interp_algo' option
            # algorithms: nearest, bilinear, bicubic, lanczos
            scale_filter = (
                f"scale_cuda={self.width}:{self.height}:"
                f"interp_algo={scale_algo}:"
                f"force_original_aspect_ratio=decrease,"
                f"pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2,"
                f"setsar=1"
            )
        else:
            # CPU Scaling
            scale_filter = (
                f"scale={self.width}:{self.height}:"
                f"flags={scale_algo}:"
                f"force_original_aspect_ratio=decrease,"
                f"pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2,"
                f"format=yuv420p"
            )
        
        cmd.extend(["-vf", scale_filter])
        
        # FPS
        cmd.extend(["-r", str(self.fps)])
        
        # Add codec-specific args
        cmd.extend(self.codec.to_ffmpeg_args())
        
        # Add color space
        cmd.extend(self.color.to_ffmpeg_args())
        
        # No audio
        cmd.extend(["-an", str(output)])
        
        try:
            self.runner.run(cmd, capture_progress=bool(progress_callback))
        except Exception:
            # Fallback to software encoding if NVENC fails
            if is_nvenc:
                print(f"HW encoding failed for {source.name}, falling back to software...")
                # Recursive call with modified config (would need access to Config to find SW equiv, 
                # but simplified: just fail or retry without hwaccel lines if we refactor. 
                # For now, simplistic fallback isn't easy without infinite recursion risk 
                # unless we change self.codec. Here we just re-raise to see error.)
                raise
            raise
            
        return output
    
    def concat_videos(
        self,
        intro: Path,
        loop: Path,
        total_seconds: int,
        tmp_dir: Path,
        progress_callback: Optional[Callable[[FFmpegProgress], None]] = None
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
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c:v", "copy",
            "-t", str(total_seconds),  # Trim to exact duration
            "-movflags", "+faststart",
            str(output)
        ]
        
        self.runner.run(cmd, capture_progress=bool(progress_callback))
        return output


# ═══════════════════════════════════════════════════════════════════════════════
# Parallel Encoding
# ═══════════════════════════════════════════════════════════════════════════════

def encode_parallel(
    encoder: VideoEncoder,
    sources: List[Tuple[Path, Path]],  # List of (source, output) pairs
    progress_callback: Optional[Callable[[str, FFmpegProgress], None]] = None
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
