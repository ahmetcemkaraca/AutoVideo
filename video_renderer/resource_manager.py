#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Resource Management System.

Manages FFmpeg processes and temporary files with graceful shutdown support.
This module ensures proper cleanup of resources even when the application
is terminated unexpectedly.

Key Features:
- Process tracking and cleanup on exit
- Temporary file tracking and cleanup
- Signal handling for graceful shutdown
- Thread-safe resource registration
- Automatic cleanup via atexit
"""

import os
import sys
import signal
import atexit
import subprocess
import threading
from pathlib import Path
from typing import Set, Optional, List, Callable
import logging

logger = logging.getLogger(__name__)


class ProcessInfo:
    """
    Information about a tracked process.

    Attributes:
        proc: The subprocess.Popen object
        pid: Process ID
        name: Human-readable name for the process
        created_at: Timestamp when process was created
    """

    def __init__(self, proc: subprocess.Popen, name: str = ""):
        self.proc = proc
        self.pid = proc.pid
        self.name = name or f"process_{proc.pid}"
        self.created_at = None  # Could add timestamp if needed

    def __repr__(self) -> str:
        return f"ProcessInfo(pid={self.pid}, name={self.name})"


class ResourceManager:
    """
    Manage FFmpeg processes and temporary files with graceful shutdown.

    This class provides centralized resource management for the video
    rendering system, ensuring proper cleanup even on unexpected termination.

    Features:
    - Process tracking and cleanup on exit
    - Temporary file tracking and cleanup
    - Signal handling (SIGTERM, SIGINT) for graceful shutdown
    - Thread-safe resource registration
    - Automatic cleanup via atexit

    Usage:
        rm = ResourceManager()
        proc = subprocess.Popen(["ffmpeg", ...])
        rm.register_process(proc, name="video_encoder")

        temp_file = Path("tmp/temp.mp4")
        rm.register_temp_file(temp_file)

        # Automatic cleanup on exit or signal
    """

    def __init__(self, enable_signals: bool = True):
        """
        Initialize resource manager.

        Args:
            enable_signals: Enable signal handlers for graceful shutdown
        """
        self._processes: dict[int, ProcessInfo] = {}
        self._temp_files: set[Path] = set()
        self._cleanup_callbacks: list[Callable] = []
        self._lock = threading.RLock()
        self._shutting_down = False

        # Register cleanup on exit
        atexit.register(self.cleanup)

        # Setup signal handlers if enabled
        if enable_signals:
            self._setup_signal_handlers()

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        # Signals to handle
        signals = []
        if hasattr(signal, "SIGTERM"):
            signals.append(signal.SIGTERM)
        if hasattr(signal, "SIGINT"):
            signals.append(signal.SIGINT)

        # Register handlers
        for sig in signals:
            signal.signal(sig, self._signal_handler)

    def _signal_handler(self, signum, frame) -> None:
        """
        Handle termination signals.

        Attempts graceful shutdown first, then exits.
        """
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.cleanup()

        # Exit with appropriate code
        sig_name = signal.Signals(signum).name if hasattr(signal, "Signals") else str(signum)
        logger.info(f"Exiting due to {sig_name}")
        sys.exit(0)

    def register_process(
        self, proc: subprocess.Popen, name: str = "", auto_cleanup: bool = True
    ) -> None:
        """
        Register a process for tracking.

        Args:
            proc: Subprocess.Popen object
            name: Human-readable name for the process
            auto_cleanup: Whether to terminate on cleanup
        """
        with self._lock:
            if self._shutting_down:
                logger.warning("Cannot register process during shutdown")
                return

            info = ProcessInfo(proc, name)
            self._processes[proc.pid] = info
            logger.debug(f"Registered process: {info}")

    def unregister_process(self, pid: int) -> None:
        """
        Unregister a process (if it completed successfully).

        Args:
            pid: Process ID to unregister
        """
        with self._lock:
            if pid in self._processes:
                info = self._processes.pop(pid)
                logger.debug(f"Unregistered process: {info}")

    def register_temp_file(self, path: Path, auto_cleanup: bool = True) -> None:
        """
        Register a temporary file for cleanup.

        Args:
            path: Path to temporary file
            auto_cleanup: Whether to delete on cleanup
        """
        with self._lock:
            if self._shutting_down:
                logger.warning("Cannot register temp file during shutdown")
                return

            self._temp_files.add(path)
            logger.debug(f"Registered temp file: {path}")

    def unregister_temp_file(self, path: Path) -> None:
        """
        Unregister a temporary file (if it should be kept).

        Args:
            path: Path to temporary file
        """
        with self._lock:
            self._temp_files.discard(path)
            logger.debug(f"Unregistered temp file: {path}")

    def register_cleanup_callback(self, callback: Callable) -> None:
        """
        Register a custom cleanup callback.

        Callbacks are invoked during cleanup in reverse registration order.

        Args:
            callback: Function to call during cleanup
        """
        with self._lock:
            self._cleanup_callbacks.append(callback)

    def get_process_count(self) -> int:
        """Get number of tracked processes."""
        with self._lock:
            return len(self._processes)

    def get_temp_file_count(self) -> int:
        """Get number of tracked temp files."""
        with self._lock:
            return len(self._temp_files)

    def get_processes(self) -> List[ProcessInfo]:
        """Get list of all tracked processes."""
        with self._lock:
            return list(self._processes.values())

    def get_temp_files(self) -> Set[Path]:
        """Get set of all tracked temp files."""
        with self._lock:
            return self._temp_files.copy()

    def terminate_process(self, pid: int, timeout: float = 5.0) -> bool:
        """
        Terminate a specific process.

        Args:
            pid: Process ID to terminate
            timeout: Seconds to wait before force killing

        Returns:
            True if process was terminated
        """
        with self._lock:
            if pid not in self._processes:
                return False

            info = self._processes[pid]
            proc = info.proc

            try:
                # Try graceful termination first
                proc.terminate()

                # Wait for process to exit
                try:
                    proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    # Force kill if didn't exit
                    logger.warning(f"Process {pid} did not exit gracefully, killing...")
                    proc.kill()
                    proc.wait()

                logger.info(f"Terminated process: {info}")
                return True

            except Exception as e:
                logger.error(f"Error terminating process {pid}: {e}")
                return False

    def terminate_all_processes(self, timeout: float = 5.0) -> int:
        """
        Terminate all tracked processes.

        Args:
            timeout: Seconds to wait before force killing each process

        Returns:
            Number of processes terminated
        """
        with self._lock:
            pids = list(self._processes.keys())

        count = 0
        for pid in pids:
            if self.terminate_process(pid, timeout):
                count += 1

        return count

    def cleanup_temp_files(self) -> int:
        """
        Delete all tracked temporary files.

        Returns:
            Number of files deleted
        """
        with self._lock:
            paths = self._temp_files.copy()

        count = 0
        for path in paths:
            try:
                if path.exists():
                    if path.is_file():
                        path.unlink()
                    elif path.is_dir():
                        # Remove directory recursively
                        import shutil

                        shutil.rmtree(path)
                    count += 1
                    logger.debug(f"Deleted temp file: {path}")
            except Exception as e:
                logger.error(f"Error deleting temp file {path}: {e}")

        return count

    def cleanup(self) -> None:
        """
        Cleanup all resources.

        This method is called automatically on exit or when receiving
        termination signals. It can also be called manually.

        Order of operations:
        1. Invoke custom cleanup callbacks
        2. Terminate all processes
        3. Delete all temporary files
        """
        with self._lock:
            if self._shutting_down:
                # Already shutting down, prevent recursion
                return
            self._shutting_down = True

        logger.info("Starting resource cleanup...")

        # Invoke custom callbacks first (in reverse order)
        callbacks = self._cleanup_callbacks[::-1]
        for callback in callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in cleanup callback: {e}")

        # Terminate processes
        proc_count = self.terminate_all_processes()
        logger.info(f"Terminated {proc_count} processes")

        # Delete temp files
        file_count = self.cleanup_temp_files()
        logger.info(f"Deleted {file_count} temporary files")

        # Restore terminal state (FFmpeg/Rich may corrupt echo settings)
        try:
            import sys
            if sys.platform != "win32":
                import os
                os.system("stty sane 2>/dev/null")
        except Exception:
            pass

        logger.info("Resource cleanup complete")

    @property
    def is_shutting_down(self) -> bool:
        """Check if cleanup is in progress."""
        with self._lock:
            return self._shutting_down

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - automatic cleanup."""
        self.cleanup()
        return False

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"ResourceManager("
            f"processes={self.get_process_count()}, "
            f"temp_files={self.get_temp_file_count()})"
        )


class TempFile:
    """
    Context manager for temporary files with auto-cleanup.

    Usage:
        with TempFile(Path("tmp/temp.mp4")) as f:
            # Use f.path
            process_file(f.path)
        # File automatically cleaned up
    """

    def __init__(
        self,
        path: Path,
        resource_manager: Optional[ResourceManager] = None,
        auto_cleanup: bool = True,
    ):
        """
        Initialize temp file context manager.

        Args:
            path: Path to temporary file
            resource_manager: ResourceManager to register with
            auto_cleanup: Whether to auto-cleanup on exit
        """
        self.path = path
        self._resource_manager = resource_manager
        self._auto_cleanup = auto_cleanup
        self._registered = False

    def __enter__(self) -> "TempFile":
        """Enter context and register file."""
        if self._resource_manager and self._auto_cleanup:
            self._resource_manager.register_temp_file(self.path)
            self._registered = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context and cleanup file."""
        if self._registered and self._auto_cleanup:
            if self._resource_manager:
                self._resource_manager.unregister_temp_file(self.path)

        if self._auto_cleanup:
            try:
                if self.path.exists():
                    if self.path.is_file():
                        self.path.unlink()
                    elif self.path.is_dir():
                        import shutil

                        shutil.rmtree(self.path)
            except Exception as e:
                logger.error(f"Error cleaning up temp file {self.path}: {e}")

        return False


def cleanup_directory(
    directory: Path, pattern: str = "*", max_age_seconds: Optional[float] = None
) -> int:
    """
    Cleanup files in a directory matching a pattern.

    Args:
        directory: Directory to clean
        pattern: Glob pattern to match files
        max_age_seconds: Only delete files older than this (None = all)

    Returns:
        Number of files deleted
    """
    if not directory.exists():
        return 0

    import time

    count = 0
    now = time.time()

    for path in directory.glob(pattern):
        if path.is_file():
            try:
                # Check age if specified
                if max_age_seconds is not None:
                    age = now - path.stat().st_mtime
                    if age < max_age_seconds:
                        continue

                path.unlink()
                count += 1
                logger.debug(f"Cleaned up file: {path}")

            except Exception as e:
                logger.error(f"Error cleaning up file {path}: {e}")

    return count
