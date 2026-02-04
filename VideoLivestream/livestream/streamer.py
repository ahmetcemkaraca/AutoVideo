#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FFmpeg RTMP streamer for YouTube livestream.
"""

import subprocess
import signal
import time
from pathlib import Path
from typing import List, Optional, Callable
from dataclasses import dataclass
import threading
import queue


@dataclass
class StreamStatus:
    """Current stream status."""
    is_running: bool = False
    frames_sent: int = 0
    duration_seconds: float = 0
    bitrate: str = ""
    error: Optional[str] = None


class FFmpegStreamer:
    """
    Manages FFmpeg process for RTMP streaming.
    """
    
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.status = StreamStatus()
        self._output_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
    
    def start(self, args: List[str], on_output: Optional[Callable[[str], None]] = None):
        """
        Start FFmpeg streaming process.
        
        Args:
            args: FFmpeg command arguments
            on_output: Optional callback for stderr output
        """
        if self.process and self.process.poll() is None:
            raise RuntimeError("Stream already running")
        
        self._stop_event.clear()
        self.status = StreamStatus(is_running=True)
        
        # Start FFmpeg process
        self.process = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
        )
        
        # Start output reader thread
        def read_output():
            while not self._stop_event.is_set() and self.process:
                if self.process.poll() is not None:
                    break
                    
                try:
                    line = self.process.stderr.readline()
                    if line:
                        text = line.decode("utf-8", errors="replace").strip()
                        if on_output:
                            on_output(text)
                        self._parse_progress(text)
                except Exception:
                    break
            
            self.status.is_running = False
        
        self._output_thread = threading.Thread(target=read_output, daemon=True)
        self._output_thread.start()
    
    def _parse_progress(self, line: str):
        """Parse FFmpeg progress output."""
        if "frame=" in line:
            try:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part.startswith("frame="):
                        self.status.frames_sent = int(part.split("=")[1])
                    elif part == "time=" or (i > 0 and parts[i-1] == "time="):
                        time_str = part if ":" in part else (parts[i] if i < len(parts) else "")
                        if ":" in time_str:
                            # Parse time string like 00:01:23.45
                            pass
                    elif part.startswith("bitrate="):
                        self.status.bitrate = part.split("=")[1]
            except Exception:
                pass
    
    def stop(self, timeout: float = 10.0):
        """Stop the streaming process gracefully."""
        self._stop_event.set()
        
        if self.process:
            # Send 'q' to quit gracefully
            try:
                self.process.stdin.write(b"q")
                self.process.stdin.flush()
            except Exception:
                pass
            
            # Wait for process to end
            try:
                self.process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            
            self.process = None
        
        if self._output_thread:
            self._output_thread.join(timeout=2.0)
        
        self.status.is_running = False
    
    def wait(self, timeout: Optional[float] = None) -> int:
        """Wait for stream to finish."""
        if self.process:
            try:
                return self.process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                return -1
        return 0
    
    @property
    def is_running(self) -> bool:
        """Check if stream is running."""
        if self.process:
            return self.process.poll() is None
        return False


class StreamManager:
    """
    Manages streaming with automatic restart on failure.
    """
    
    def __init__(self, max_retries: int = 5, retry_delay: float = 5.0):
        self.streamer = FFmpegStreamer()
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._should_stop = False
    
    def stream_segment(
        self,
        args: List[str],
        duration_seconds: int,
        on_status: Optional[Callable[[StreamStatus], None]] = None,
        on_output: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """
        Stream a segment with retry logic.
        
        Args:
            args: FFmpeg command arguments
            duration_seconds: Expected duration
            on_status: Status callback
            on_output: Output callback
            
        Returns:
            True if completed successfully
        """
        retries = 0
        
        while retries < self.max_retries and not self._should_stop:
            try:
                self.streamer.start(args, on_output)
                
                # Monitor progress
                start_time = time.time()
                
                while self.streamer.is_running and not self._should_stop:
                    elapsed = time.time() - start_time
                    
                    if on_status:
                        self.streamer.status.duration_seconds = elapsed
                        on_status(self.streamer.status)
                    
                    # Check if we've streamed long enough
                    if elapsed >= duration_seconds:
                        self.streamer.stop()
                        return True
                    
                    time.sleep(1.0)
                
                # Check if stream ended naturally
                if not self._should_stop:
                    exit_code = self.streamer.wait(timeout=5.0)
                    
                    if exit_code == 0:
                        return True
                    
                    # Stream failed, retry
                    retries += 1
                    if retries < self.max_retries:
                        time.sleep(self.retry_delay)
                
            except Exception as e:
                self.streamer.status.error = str(e)
                retries += 1
                if retries < self.max_retries:
                    time.sleep(self.retry_delay)
        
        return False
    
    def stop(self):
        """Stop streaming."""
        self._should_stop = True
        self.streamer.stop()
