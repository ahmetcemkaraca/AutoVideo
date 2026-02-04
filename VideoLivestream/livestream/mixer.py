#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audio/Video mixer for livestream.
Creates FFmpeg filter commands for real-time mixing.
"""

import tempfile
from pathlib import Path
from typing import List, Tuple, Optional


def create_concat_file(files: List[Path], output_path: Path) -> Path:
    """
    Create FFmpeg concat demuxer file.
    
    Args:
        files: List of media files to concatenate
        output_path: Where to save the concat file
        
    Returns:
        Path to concat file
    """
    with open(output_path, "w", encoding="utf-8") as f:
        for file in files:
            # Escape single quotes in path
            escaped = str(file.absolute()).replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")
    
    return output_path


def create_looped_concat_file(files: List[Path], output_path: Path, loop_count: int = 100) -> Path:
    """
    Create concat file that loops files multiple times.
    Used for ensuring music plays throughout the stream.
    """
    with open(output_path, "w", encoding="utf-8") as f:
        for _ in range(loop_count):
            for file in files:
                escaped = str(file.absolute()).replace("'", "'\\''")
                f.write(f"file '{escaped}'\n")
    
    return output_path


class AudioMixer:
    """
    Handles audio mixing for livestream.
    Mixes music tracks with background audio.
    """
    
    def __init__(self, tmp_dir: Path):
        self.tmp_dir = tmp_dir
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
    
    def create_music_concat(self, tracks: List[Path], loop_count: int = 50) -> Path:
        """Create concat file for music tracks (looped)."""
        concat_file = self.tmp_dir / "music_concat.txt"
        return create_looped_concat_file(tracks, concat_file, loop_count)
    
    def create_bg_concat(self, backgrounds: List[Tuple[Path, float]], loop_count: int = 100) -> Tuple[Path, str]:
        """
        Create concat file for backgrounds and return filter for gain.
        
        Returns:
            (concat_file_path, filter_string)
        """
        if not backgrounds:
            return None, ""
        
        concat_file = self.tmp_dir / "bg_concat.txt"
        
        # Just use the first background file for simplicity
        # Multiple BGs would need more complex mixing
        bg_path, gain_db = backgrounds[0]
        
        with open(concat_file, "w", encoding="utf-8") as f:
            for _ in range(loop_count):
                escaped = str(bg_path.absolute()).replace("'", "'\\''")
                f.write(f"file '{escaped}'\n")
        
        # Calculate volume multiplier from dB
        volume = 10 ** (gain_db / 20)
        filter_str = f"volume={volume:.4f}"
        
        return concat_file, filter_str
    
    def build_audio_filter(
        self,
        has_music: bool = True,
        has_bg: bool = True,
        bg_gain_db: float = -8.0
    ) -> str:
        """
        Build FFmpeg filter for audio mixing.
        
        Inputs expected:
        - [2:a] = music audio
        - [3:a] = background audio (if has_bg)
        
        Returns:
            Filter complex string
        """
        if has_music and has_bg:
            bg_volume = 10 ** (bg_gain_db / 20)
            return f"[3:a]volume={bg_volume:.4f}[bg];[2:a][bg]amix=inputs=2:duration=first:dropout_transition=3[aout]"
        elif has_music:
            return "[2:a]anull[aout]"
        elif has_bg:
            bg_volume = 10 ** (bg_gain_db / 20)
            return f"[3:a]volume={bg_volume:.4f}[aout]"
        else:
            return "anullsrc=r=48000:cl=stereo[aout]"


class VideoMixer:
    """
    Handles video mixing for livestream.
    Creates intro → loop sequence that plays continuously.
    """
    
    def __init__(self, tmp_dir: Path):
        self.tmp_dir = tmp_dir
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
    
    def build_video_filter(
        self,
        width: int = 1920,
        height: int = 1080,
        fps: int = 30
    ) -> str:
        """
        Build video filter for consistent output.
        
        The video inputs are:
        - [0:v] = intro video (plays once)
        - [1:v] = loop video (plays forever with -stream_loop -1)
        
        After intro plays, we only stream the loop.
        For simplicity, we'll just use the loop video with -stream_loop.
        """
        return f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps={fps}"


def build_ffmpeg_stream_args(
    intro_video: Path,
    loop_video: Path,
    music_concat: Path,
    bg_concat: Optional[Path],
    bg_gain_db: float,
    rtmp_url: str,
    video_bitrate: str = "4500k",
    audio_bitrate: str = "128k",
    resolution: str = "1920x1080",
    fps: int = 30,
    preset: str = "veryfast",
    duration_seconds: Optional[int] = None,
) -> List[str]:
    """
    Build complete FFmpeg command for streaming.
    
    This streams: intro once → loop forever, with music + background audio.
    
    Args:
        intro_video: Path to intro video
        loop_video: Path to loop video
        music_concat: Path to music concat file
        bg_concat: Path to background concat file (optional)
        bg_gain_db: Gain for background audio
        rtmp_url: Full RTMP URL with stream key
        duration_seconds: Optional duration limit
        
    Returns:
        FFmpeg command arguments
    """
    width, height = map(int, resolution.split("x"))
    
    args = ["ffmpeg", "-re"]
    
    # Input 0: Intro video
    args.extend(["-i", str(intro_video)])
    
    # Input 1: Loop video (infinite loop)
    args.extend(["-stream_loop", "-1", "-i", str(loop_video)])
    
    # Input 2: Music (from concat file, infinite)
    args.extend(["-f", "concat", "-safe", "0", "-stream_loop", "-1", "-i", str(music_concat)])
    
    # Input 3: Background audio (if exists)
    has_bg = bg_concat is not None and bg_concat.exists()
    if has_bg:
        args.extend(["-f", "concat", "-safe", "0", "-stream_loop", "-1", "-i", str(bg_concat)])
    
    # Build filter complex
    # Video: concat intro and loop, then scale
    video_filter = f"[0:v][1:v]concat=n=2:v=1:a=0[vraw];[vraw]scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps={fps}[vout]"
    
    # Audio: mix music with background
    if has_bg:
        bg_volume = 10 ** (bg_gain_db / 20)
        audio_filter = f"[3:a]volume={bg_volume:.4f}[bg];[2:a][bg]amix=inputs=2:duration=first:dropout_transition=3[aout]"
    else:
        audio_filter = "[2:a]anull[aout]"
    
    filter_complex = f"{video_filter};{audio_filter}"
    
    args.extend(["-filter_complex", filter_complex])
    args.extend(["-map", "[vout]", "-map", "[aout]"])
    
    # Video encoding
    args.extend([
        "-c:v", "libx264",
        "-preset", preset,
        "-b:v", video_bitrate,
        "-maxrate", video_bitrate,
        "-bufsize", str(int(video_bitrate.replace("k", "")) * 2) + "k",
        "-g", str(fps * 2),  # Keyframe every 2 seconds
    ])
    
    # Audio encoding
    args.extend([
        "-c:a", "aac",
        "-b:a", audio_bitrate,
        "-ar", "48000",
    ])
    
    # Duration limit
    if duration_seconds:
        args.extend(["-t", str(duration_seconds)])
    
    # Output
    args.extend(["-f", "flv", rtmp_url])
    
    return args


def build_segment_stream_args(
    loop_video: Path,
    music_concat: Path,
    bg_concat: Optional[Path],
    bg_gain_db: float,
    rtmp_url: str,
    duration_seconds: int,
    video_bitrate: str = "4500k",
    audio_bitrate: str = "128k",
    resolution: str = "1920x1080",
    fps: int = 30,
    preset: str = "veryfast",
) -> List[str]:
    """
    Build FFmpeg command for a single segment (loop only, no intro).
    Used for continuous streaming after intro.
    """
    width, height = map(int, resolution.split("x"))
    
    args = ["ffmpeg", "-re"]
    
    # Input 0: Loop video (looped for duration)
    args.extend(["-stream_loop", "-1", "-i", str(loop_video)])
    
    # Input 1: Music
    args.extend(["-f", "concat", "-safe", "0", "-stream_loop", "-1", "-i", str(music_concat)])
    
    # Input 2: Background (optional)
    has_bg = bg_concat is not None and bg_concat.exists()
    if has_bg:
        args.extend(["-f", "concat", "-safe", "0", "-stream_loop", "-1", "-i", str(bg_concat)])
    
    # Video filter
    video_filter = f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps={fps}[vout]"
    
    # Audio filter
    if has_bg:
        bg_volume = 10 ** (bg_gain_db / 20)
        audio_filter = f"[2:a]volume={bg_volume:.4f}[bg];[1:a][bg]amix=inputs=2:duration=first:dropout_transition=3[aout]"
    else:
        audio_filter = "[1:a]anull[aout]"
    
    filter_complex = f"{video_filter};{audio_filter}"
    
    args.extend(["-filter_complex", filter_complex])
    args.extend(["-map", "[vout]", "-map", "[aout]"])
    
    # Encoding
    args.extend([
        "-c:v", "libx264", "-preset", preset,
        "-b:v", video_bitrate, "-maxrate", video_bitrate,
        "-bufsize", str(int(video_bitrate.replace("k", "")) * 2) + "k",
        "-g", str(fps * 2),
        "-c:a", "aac", "-b:a", audio_bitrate, "-ar", "48000",
    ])
    
    # Duration
    args.extend(["-t", str(duration_seconds)])
    
    # Output
    args.extend(["-f", "flv", rtmp_url])
    
    return args
