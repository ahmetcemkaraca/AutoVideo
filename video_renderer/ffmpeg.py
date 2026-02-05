#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FFmpeg subprocess runner with progress parsing and logging.
"""

import re
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any


# ═══════════════════════════════════════════════════════════════════════════════
# Data Types
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class VideoInfo:
    """Information about a video stream."""
    codec: str
    width: int
    height: int
    fps: str
    duration: float
    pix_fmt: str
    color_space: Optional[str] = None
    color_primaries: Optional[str] = None
    color_transfer: Optional[str] = None
    profile: Optional[str] = None


@dataclass
class FFmpegProgress:
    """Progress information from FFmpeg."""
    frame: int = 0
    fps: float = 0.0
    time_seconds: float = 0.0
    speed: float = 0.0
    size_kb: int = 0
    bitrate_kbps: float = 0.0
    percent: float = 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# FFmpeg Runner
# ═══════════════════════════════════════════════════════════════════════════════

class FFmpegRunner:
    """
    Runs FFmpeg commands with progress parsing and logging.
    """
    
    def __init__(self, log_path: Optional[Path] = None):
        self.log_path = log_path
        self._progress_callback: Optional[Callable[[FFmpegProgress], None]] = None
        self._total_duration: float = 0.0
    
    def set_progress_callback(self, callback: Callable[[FFmpegProgress], None]):
        """Set a callback for progress updates."""
        self._progress_callback = callback
    
    def set_total_duration(self, duration: float):
        """Set total duration for percent calculation."""
        self._total_duration = duration
    
    def _log_command(self, cmd: List[str]):
        """Log a command to the log file."""
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as f:
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"\n[{timestamp}] $ {' '.join(shlex.quote(c) for c in cmd)}\n")
    
    def _parse_progress_line(self, line: str) -> Optional[FFmpegProgress]:
        """Parse an FFmpeg progress line."""
        progress = FFmpegProgress()
        
        # frame=  123 fps= 45.6 q=28.0 size=    1234kB time=00:01:23.45 bitrate= 123.4kbits/s speed=1.23x
        patterns = {
            'frame': r'frame=\s*(\d+)',
            'fps': r'fps=\s*([\d.]+)',
            'size': r'size=\s*(\d+)kB',
            'time': r'time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})',
            'bitrate': r'bitrate=\s*([\d.]+)kbits/s',
            'speed': r'speed=\s*([0-9\.eE\+\-]+)x',
        }
        
        if match := re.search(patterns['frame'], line):
            progress.frame = int(match.group(1))
        
        if match := re.search(patterns['fps'], line):
            progress.fps = float(match.group(1))
        
        if match := re.search(patterns['size'], line):
            progress.size_kb = int(match.group(1))
        
        if match := re.search(patterns['time'], line):
            h, m, s, cs = map(int, match.groups())
            progress.time_seconds = h * 3600 + m * 60 + s + cs / 100
        
        if match := re.search(patterns['bitrate'], line):
            progress.bitrate_kbps = float(match.group(1))
        
        if match := re.search(patterns['speed'], line):
            progress.speed = float(match.group(1))
        
        # Calculate percent if we have duration
        if self._total_duration > 0 and progress.time_seconds > 0:
            progress.percent = min(100.0, (progress.time_seconds / self._total_duration) * 100)
        
        return progress if progress.frame > 0 or progress.time_seconds > 0 else None
    
    def run(self, cmd: List[str], capture_progress: bool = True) -> subprocess.CompletedProcess:
        """
        Run an FFmpeg command.
        
        Args:
            cmd: Command and arguments
            capture_progress: If True, parse and report progress
            
        Returns:
            CompletedProcess result
            
        Raises:
            subprocess.CalledProcessError: If command fails
        """
        self._log_command(cmd)
        
        if not capture_progress or not self._progress_callback:
            return subprocess.run(cmd, check=True)
        
        # Run with progress parsing
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        stderr_lines = []
        
        # FFmpeg writes progress to stderr
        for line in iter(process.stderr.readline, ''):
            stderr_lines.append(line)
            
            if progress := self._parse_progress_line(line):
                self._progress_callback(progress)
        
        process.wait()
        
        if process.returncode != 0:
            raise subprocess.CalledProcessError(
                process.returncode,
                cmd,
                output=process.stdout.read() if process.stdout else "",
                stderr="".join(stderr_lines)
            )
        
        return subprocess.CompletedProcess(
            cmd,
            process.returncode,
            stdout="",
            stderr="".join(stderr_lines)
        )
    
    def run_simple(self, cmd: List[str]) -> subprocess.CompletedProcess:
        """Run a command without progress tracking."""
        self._log_command(cmd)
        return subprocess.run(cmd, check=True, capture_output=True, text=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Probe Functions
# ═══════════════════════════════════════════════════════════════════════════════

def probe_video(path: Path) -> VideoInfo:
    """
    Get video stream information using ffprobe.
    
    Args:
        path: Path to video file
        
    Returns:
        VideoInfo with stream details
    """
    fields = [
        "codec_name", "width", "height", "pix_fmt", "r_frame_rate",
        "color_space", "color_primaries", "color_transfer", "profile"
    ]
    
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=" + ",".join(fields),
        "-of", "default=noprint_wrappers=1:nokey=0",
        str(path)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    
    kv: Dict[str, str] = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if "=" in line:
            k, v = line.split("=", 1)
            kv[k.strip()] = v.strip()
    
    # Parse fps
    fps_str = kv.get("r_frame_rate", "0/1")
    
    return VideoInfo(
        codec=kv.get("codec_name", "unknown"),
        width=int(kv.get("width", 0)),
        height=int(kv.get("height", 0)),
        fps=fps_str,
        duration=get_duration(path),
        pix_fmt=kv.get("pix_fmt", "unknown"),
        color_space=kv.get("color_space"),
        color_primaries=kv.get("color_primaries"),
        color_transfer=kv.get("color_transfer"),
        profile=kv.get("profile"),
    )


def get_duration(path: Path) -> float:
    """Get media duration in seconds."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def write_concat_list(files: List[Path], output_path: Path) -> None:
    """Write a concat demuxer file list."""
    lines = [f"file '{p.resolve().as_posix()}'" for p in files]
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
