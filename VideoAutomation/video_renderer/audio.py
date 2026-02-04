#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audio processing: looping, mixing, gain adjustment.
"""

import re
from pathlib import Path
from typing import List, Tuple, Optional, Callable

from .ffmpeg import FFmpegRunner, FFmpegProgress, get_duration, write_concat_list


# ═══════════════════════════════════════════════════════════════════════════════
# Audio Utilities
# ═══════════════════════════════════════════════════════════════════════════════

def is_background_file(path: Path) -> bool:
    """Check if file is a background audio (starts with 'bg')."""
    return path.stem.lower().startswith("bg")


def parse_background_gain_db(path: Path) -> float:
    """
    Parse gain in dB from background filename.
    Examples: bg_-8.5.mp3 -> -8.5, bg_+2.wav -> +2, bg-1.flac -> -1
    """
    name = path.stem
    match = re.search(r"bg[_-]([+-]?\d+(?:\.\d+)?)", name, re.IGNORECASE)
    if match:
        return float(match.group(1))
    return 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# Audio Processor
# ═══════════════════════════════════════════════════════════════════════════════

class AudioProcessor:
    """
    Handles audio processing operations.
    """
    
    # Audio format for intermediate processing (high quality, large file support)
    INTERMEDIATE_FORMAT = "w64"  # Wave64 for >4GB files
    INTERMEDIATE_CODEC = "pcm_s16le"
    SAMPLE_RATE = 48000
    
    def __init__(self, runner: FFmpegRunner, tmp_dir: Path):
        self.runner = runner
        self.tmp_dir = tmp_dir
    
    def create_music_loop(
        self,
        tracks: List[Path],
        total_seconds: int,
        progress_callback: Optional[Callable[[FFmpegProgress], None]] = None
    ) -> Path:
        """
        Create a looped music track from multiple tracks.
        
        Args:
            tracks: List of music tracks to loop
            total_seconds: Target duration
            progress_callback: Optional progress callback
            
        Returns:
            Path to looped audio file
        """
        # Write concat list
        music_list = self.tmp_dir / "music_list.txt"
        write_concat_list(tracks, music_list)
        
        output = self.tmp_dir / f"music_loop.{self.INTERMEDIATE_FORMAT}"
        
        if progress_callback:
            self.runner.set_total_duration(total_seconds)
            self.runner.set_progress_callback(progress_callback)
        
        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", "-1",
            "-f", "concat", "-safe", "0",
            "-i", str(music_list),
            "-t", str(total_seconds),
            "-c:a", self.INTERMEDIATE_CODEC,
            "-ar", str(self.SAMPLE_RATE),
            "-f", self.INTERMEDIATE_FORMAT,
            str(output)
        ]
        
        self.runner.run(cmd, capture_progress=bool(progress_callback))
        return output
    
    def apply_gain(
        self,
        source: Path,
        gain_db: float,
        output_name: Optional[str] = None
    ) -> Path:
        """
        Apply gain adjustment to an audio file.
        
        Args:
            source: Source audio path
            gain_db: Gain in decibels (negative to reduce volume)
            output_name: Optional output filename
            
        Returns:
            Path to processed audio file
        """
        if output_name is None:
            safe_name = re.sub(r"[^a-zA-Z0-9_.+-]+", "_", source.stem)
            output_name = f"{safe_name}_gain.{self.INTERMEDIATE_FORMAT}"
        
        output = self.tmp_dir / output_name
        
        cmd = [
            "ffmpeg", "-y",
            "-i", str(source),
            "-filter:a", f"volume={gain_db}dB",
            "-c:a", self.INTERMEDIATE_CODEC,
            "-ar", str(self.SAMPLE_RATE),
            "-f", self.INTERMEDIATE_FORMAT,
            str(output)
        ]
        
        self.runner.run_simple(cmd)
        return output
    
    def mix_tracks(
        self,
        main_track: Path,
        background_tracks: List[Path],
        total_seconds: int,
        progress_callback: Optional[Callable[[FFmpegProgress], None]] = None
    ) -> Path:
        """
        Mix main track with background tracks.
        
        Args:
            main_track: Primary audio track
            background_tracks: List of background audio tracks
            total_seconds: Target duration
            progress_callback: Optional progress callback
            
        Returns:
            Path to mixed audio file
        """
        if not background_tracks:
            return main_track
        
        output = self.tmp_dir / f"audio_mixed.{self.INTERMEDIATE_FORMAT}"
        
        if progress_callback:
            self.runner.set_total_duration(total_seconds)
            self.runner.set_progress_callback(progress_callback)
        
        # Build command with all inputs
        cmd = ["ffmpeg", "-y", "-i", str(main_track)]
        
        for bg in background_tracks:
            cmd.extend(["-stream_loop", "-1", "-i", str(bg)])
        
        # Mix all inputs
        input_count = 1 + len(background_tracks)
        filter_complex = f"amix=inputs={input_count}:duration=shortest:normalize=0"
        
        cmd.extend([
            "-filter_complex", filter_complex,
            "-t", str(total_seconds),
            "-c:a", self.INTERMEDIATE_CODEC,
            "-ar", str(self.SAMPLE_RATE),
            "-f", self.INTERMEDIATE_FORMAT,
            str(output)
        ])
        
        self.runner.run(cmd, capture_progress=bool(progress_callback))
        return output
    
    def process_backgrounds(
        self,
        backgrounds: List[Tuple[Path, float]]
    ) -> List[Path]:
        """
        Process background audio files with gain adjustment.
        
        Args:
            backgrounds: List of (path, gain_db) tuples
            
        Returns:
            List of processed background audio paths
        """
        processed = []
        for path, gain_db in backgrounds:
            safe_name = re.sub(r"[^a-zA-Z0-9_.+-]+", "_", path.stem)
            output = self.apply_gain(
                path,
                gain_db,
                f"{safe_name}_bg.{self.INTERMEDIATE_FORMAT}"
            )
            processed.append(output)
        return processed


# ═══════════════════════════════════════════════════════════════════════════════
# Final Muxer
# ═══════════════════════════════════════════════════════════════════════════════

def mux_video_audio(
    runner: FFmpegRunner,
    video: Path,
    audio: Path,
    output: Path,
    audio_bitrate: str = "192k",
    progress_callback: Optional[Callable[[FFmpegProgress], None]] = None
) -> Path:
    """
    Mux video and audio into final output.
    
    Args:
        runner: FFmpeg runner instance
        video: Video-only file path
        audio: Audio file path
        output: Final output path
        audio_bitrate: AAC audio bitrate
        progress_callback: Optional progress callback
        
    Returns:
        Output path
    """
    if progress_callback:
        duration = get_duration(video)
        runner.set_total_duration(duration)
        runner.set_progress_callback(progress_callback)
    
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video),
        "-i", str(audio),
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", audio_bitrate,
        "-shortest",
        "-movflags", "+faststart",
        str(output)
    ]
    
    runner.run(cmd, capture_progress=bool(progress_callback))
    return output
