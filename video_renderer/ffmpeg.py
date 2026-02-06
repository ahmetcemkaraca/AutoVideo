#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FFmpeg subprocess runner with progress parsing and logging.

OPTIMIZED VERSION:
- Reduced memory overhead via streaming output handling
- Optimized regex patterns with pre-compilation
- Added retry mechanism and graceful degradation
- Improved GPU utilization through hardware acceleration options
- Better error handling with detailed diagnostics
"""

import re
import shlex
import subprocess
import time
import threading
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Tuple


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
# Pre-compiled Regex Patterns for Performance
# ═══════════════════════════════════════════════════════════════════════════════

# Pre-compile all regex patterns to avoid repeated compilation overhead
PROGRESS_PATTERNS = {
    'frame': re.compile(r'frame=\s*(\d+)'),
    'fps': re.compile(r'fps=\s*([\d.]+)'),
    'size': re.compile(r'size=\s*(\d+)kB'),
    'time': re.compile(r'time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})'),
    'bitrate': re.compile(r'bitrate=\s*([\d.]+)kbits/s'),
    'speed': re.compile(r'speed=\s*([0-9\.eE\+\-]+)x'),
}

# Pattern for extracting error information from FFmpeg stderr
ERROR_PATTERNS = {
    'hardware_error': re.compile(r'Error (?:initializing|opening|getting) .*? (?:NVENC|CUDA|QSV|VAAPI)', re.IGNORECASE),
    'memory_error': re.compile(r'(Cannot allocate memory|Out of memory|memory allocation failed)', re.IGNORECASE),
    'io_error': re.compile(r'(I/O error|Read error|Write error|Permission denied)', re.IGNORECASE),
    'codec_error': re.compile(r'(Unknown codec|Unsupported codec|Codec not found)', re.IGNORECASE),
}

# ═══════════════════════════════════════════════════════════════════════════════
# FFmpeg Runner
# ═══════════════════════════════════════════════════════════════════════════════

class FFmpegRunner:
    """
    OPTIMIZED FFmpeg command runner with:
    - Streaming progress parsing (reduced memory)
    - Retry mechanism with exponential backoff
    - Hardware acceleration fallback
    - Detailed error diagnostics
    - Thread-safe callback handling
    """

    # Class-level cache for encoder availability
    _encoder_cache: Dict[str, bool] = {}
    _cache_lock = threading.Lock()

    def __init__(self, log_path: Optional[Path] = None, max_retries: int = 3):
        self.log_path = log_path
        self._progress_callback: Optional[Callable[[FFmpegProgress], None]] = None
        self._total_duration: float = 0.0
        self._max_retries = max_retries
        self._callback_lock = threading.Lock()
        # Circular buffer for last N stderr lines (memory optimization)
        self._stderr_buffer: deque[str] = deque(maxlen=100)
    
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
        """
        OPTIMIZED: Parse an FFmpeg progress line using pre-compiled regex.

        Performance improvements:
        - Uses pre-compiled regex patterns (module-level constants)
        - Early return on non-progress lines
        - Single-pass parsing with dict lookups
        """
        # Fast-path: skip lines without progress indicators
        if 'frame=' not in line:
            return None

        progress = FFmpegProgress()

        # Use pre-compiled patterns
        if match := PROGRESS_PATTERNS['frame'].search(line):
            progress.frame = int(match.group(1))

        if match := PROGRESS_PATTERNS['fps'].search(line):
            progress.fps = float(match.group(1))

        if match := PROGRESS_PATTERNS['size'].search(line):
            progress.size_kb = int(match.group(1))

        if match := PROGRESS_PATTERNS['time'].search(line):
            h, m, s, cs = map(int, match.groups())
            progress.time_seconds = h * 3600 + m * 60 + s + cs / 100

        if match := PROGRESS_PATTERNS['bitrate'].search(line):
            progress.bitrate_kbps = float(match.group(1))

        if match := PROGRESS_PATTERNS['speed'].search(line):
            progress.speed = float(match.group(1))

        # Calculate percent if we have duration
        if self._total_duration > 0 and progress.time_seconds > 0:
            progress.percent = min(100.0, (progress.time_seconds / self._total_duration) * 100)

        return progress if progress.frame > 0 or progress.time_seconds > 0 else None

    def _detect_hardware_failure(self, stderr_lines: List[str]) -> Tuple[bool, str]:
        """
        Detect if the failure was hardware-related and should trigger fallback.

        Returns:
            (is_hardware_failure, fallback_reason)
        """
        stderr_text = '\n'.join(stderr_lines[-50:])  # Check last 50 lines

        for error_type, pattern in ERROR_PATTERNS.items():
            if pattern.search(stderr_text):
                if error_type == 'hardware_error':
                    return True, f"Hardware encoder failed: {pattern.search(stderr_text).group(0)}"
                elif error_type == 'memory_error':
                    return True, "GPU memory exhausted"

        return False, ""

    def _build_fallback_command(self, cmd: List[str]) -> Optional[List[str]]:
        """
        Build a software fallback command by removing hardware acceleration flags.

        Returns:
            Modified command for software encoding, or None if no fallback possible
        """
        # Find and remove hardware acceleration flags
        hw_flags = {'-hwaccel', '-hwaccel_output_format', '-vaapi_device'}
        fallback_cmd = []

        skip_next = False
        for i, arg in enumerate(cmd):
            if skip_next:
                skip_next = False
                continue

            if arg in hw_flags:
                skip_next = True
                continue

            # Replace hardware encoders with software equivalents
            if arg.endswith('_nvenc') or arg.endswith('_qsv') or arg.endswith('_vaapi'):
                if 'av1' in arg.lower():
                    fallback_cmd.append('libsvtav1')
                elif 'hevc' in arg.lower() or 'h265' in arg.lower():
                    fallback_cmd.append('libx265')
                elif 'h264' in arg.lower():
                    fallback_cmd.append('libx264')
                else:
                    fallback_cmd.append(arg)  # Keep unknown encoders
            else:
                fallback_cmd.append(arg)

        return fallback_cmd if fallback_cmd != cmd else None
    
    def run(self, cmd: List[str], capture_progress: bool = True) -> subprocess.CompletedProcess:
        """
        OPTIMIZED: Run an FFmpeg command with retry and fallback support.

        Improvements:
        - Retry mechanism with exponential backoff
        - Automatic hardware → software fallback on GPU errors
        - Memory-efficient streaming output handling
        - Thread-safe progress callbacks

        Args:
            cmd: Command and arguments
            capture_progress: If True, parse and report progress

        Returns:
            CompletedProcess result

        Raises:
            subprocess.CalledProcessError: If command fails after all retries
        """
        self._log_command(cmd)

        if not capture_progress or not self._progress_callback:
            return subprocess.run(cmd, check=True)

        # Retry loop with exponential backoff
        for attempt in range(self._max_retries):
            try:
                return self._run_once(cmd, capture_progress)
            except subprocess.CalledProcessError as e:
                # Check if this is a hardware failure that merits fallback
                is_hw_failure, reason = self._detect_hardware_failure(self._stderr_buffer)

                if is_hw_failure and attempt < self._max_retries - 1:
                    # Try software fallback
                    fallback_cmd = self._build_fallback_command(cmd)
                    if fallback_cmd:
                        print(f"[WARN] {reason}. Falling back to software encoding...")
                        try:
                            return self._run_once(fallback_cmd, capture_progress)
                        except subprocess.CalledProcessError:
                            pass  # Fall through to retry

                if attempt == self._max_retries - 1:
                    # Last attempt failed, raise the exception
                    raise e

                # Exponential backoff
                wait_time = 2 ** attempt * 0.5  # 0.5s, 1s, 2s...
                print(f"[WARN] FFmpeg attempt {attempt + 1} failed. Retrying in {wait_time}s...")
                time.sleep(wait_time)

        # Shouldn't reach here, but just in case
        raise subprocess.CalledProcessError(1, cmd)

    def _run_once(self, cmd: List[str], capture_progress: bool) -> subprocess.CompletedProcess:
        """
        Single FFmpeg execution attempt.

        OPTIMIZED: Uses streaming readline to avoid loading entire stderr into memory.
        """
        # Run with progress parsing
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1  # Line buffered
        )

        # Clear and reuse buffer
        self._stderr_buffer.clear()

        # FFmpeg writes progress to stderr
        for line in iter(process.stderr.readline, ''):
            # Only keep recent lines in memory (circular buffer)
            self._stderr_buffer.append(line)

            # Parse progress (fast-path on non-progress lines)
            if progress := self._parse_progress_line(line):
                # Thread-safe callback
                with self._callback_lock:
                    if self._progress_callback:
                        self._progress_callback(progress)

        process.wait()

        if process.returncode != 0:
            raise subprocess.CalledProcessError(
                process.returncode,
                cmd,
                output="",
                stderr="\n".join(self._stderr_buffer)
            )

        return subprocess.CompletedProcess(
            cmd,
            process.returncode,
            stdout="",
            stderr="\n".join(self._stderr_buffer)
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
