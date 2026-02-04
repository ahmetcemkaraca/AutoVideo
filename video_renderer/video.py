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

    def is_compatible(self, source: Path) -> bool:
        """Check if source video is already compatible."""
        try:
            info = probe_video(source)
            
            # 1. Resolution
            if info.width != self.width or info.height != self.height:
                return False
                
            # 2. Codec
            expected_codec = self._get_expected_codec_name()
            if info.codec.lower() != expected_codec:
                return False
                
            # 3. FPS (approximate check)
            source_fps = self._parse_fps(info.fps)
            if abs(source_fps - self.fps) > 0.05: # Allow small variance (e.g. 59.94 vs 60 if needed, but here strict)
                return False
                
            # 4. Pixel Format
            if info.pix_fmt not in ("yuv420p", "yuvj420p"):
                return False
                
            return True
        except Exception:
            return False

    def normalize_video(
        self,
        source: Path,
        output: Path,
        progress_callback: Optional[Callable[[FFmpegProgress], None]] = None
    ) -> Path:
        """
        Normalize a video to target specs (resolution, fps, codec, color).
        Skips re-encoding if source is already compatible.
        
        Args:
            source: Source video path
            output: Output path
            progress_callback: Optional callback for progress updates
            
        Returns:
            Output path
        """
        if progress_callback:
            duration = get_duration(source)
            self.runner.set_total_duration(duration)
            self.runner.set_progress_callback(progress_callback)
        
        # Check compatibility
        if self.is_compatible(source):
            try:
                # Direct copy
                shutil.copy2(source, output)
                
                # Report 100% progress
                if progress_callback:
                    p = FFmpegProgress(
                        percent=100.0,
                        time_seconds=get_duration(source),
                        fps=0.0,
                        speed=float('inf')
                    )
                    progress_callback(p)
                    
                return output
            except Exception as e:
                # Fallback to encode if copy fails
                pass

        # Build filter chain
        scale_filter = (
            f"scale={self.width}:{self.height}:"
            f"force_original_aspect_ratio=decrease,"
            f"pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2,"
            f"format=yuv420p"
        )
        
        cmd = [
            "ffmpeg", "-y",
            "-i", str(source),
            "-vf", scale_filter,
            "-r", str(self.fps),
        ]
        
        # Add codec-specific args
        cmd.extend(self.codec.to_ffmpeg_args())
        
        # Add color space
        cmd.extend(self.color.to_ffmpeg_args())
        
        # No audio
        cmd.extend(["-an", str(output)])
        
        self.runner.run(cmd, capture_progress=bool(progress_callback))
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
