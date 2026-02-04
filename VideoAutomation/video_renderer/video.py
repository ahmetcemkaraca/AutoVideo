#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video processing: encoding, normalization, and concatenation.
"""

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
    
    def normalize_video(
        self,
        source: Path,
        output: Path,
        progress_callback: Optional[Callable[[FFmpegProgress], None]] = None
    ) -> Path:
        """
        Normalize a video to target specs (resolution, fps, codec, color).
        
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
