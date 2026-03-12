#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Terminal utilities for clean output and proper cleanup.

Handles:
- Terminal state management (Windows/Unix)
- Clean process execution with organized output
- Progress tracking and formatted output
- Proper signal handling and cleanup
"""

import os
import sys
import subprocess
import time
import threading
import atexit
import signal
from pathlib import Path
from typing import Optional, List, Callable, Any
from dataclasses import dataclass
from io import StringIO


@dataclass
class ProcessOutput:
    """Container for subprocess output."""
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0


class TerminalManager:
    """Manages terminal state and cleanup on Windows/Unix."""

    def __init__(self):
        self.original_signals = {}
        self.is_windows = sys.platform == "win32"
        self._setup_cleanup()

    def _setup_cleanup(self):
        """Setup proper cleanup handlers."""
        atexit.register(self.cleanup)
        
        # Setup signal handlers
        if not self.is_windows:
            signal.signal(signal.SIGTERM, self._signal_handler)
            signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle termination signals."""
        self.cleanup()
        sys.exit(0)

    def cleanup(self):
        """Restore terminal state on exit."""
        if self.is_windows:
            # Windows: Restore console mode
            try:
                # Enable echo and disable raw input on Windows
                os.system("cls" if self.is_windows else "clear")
            except Exception:
                pass
        else:
            # Unix: Restore terminal settings
            try:
                os.system("stty sane 2>/dev/null || true")
            except Exception:
                pass
        
        # Flush all streams
        sys.stdout.flush()
        sys.stderr.flush()

    def run_clean(
        self,
        cmd: List[str],
        task_name: str = "",
        capture_output: bool = False,
        timeout: Optional[float] = None,
    ) -> ProcessOutput:
        """
        Run a subprocess with clean output formatting.
        
        Args:
            cmd: Command and arguments
            task_name: Human-readable task name for logging
            capture_output: If True, capture stdout/stderr
            timeout: Process timeout in seconds
            
        Returns:
            ProcessOutput with stdout, stderr, and returncode
        """
        if task_name:
            self._print_task_header(task_name)
        
        try:
            if capture_output:
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=timeout,
                    stdin=subprocess.DEVNULL if sys.platform == "win32" else None,
                )
                return ProcessOutput(
                    stdout=result.stdout,
                    stderr=result.stderr,
                    returncode=result.returncode,
                )
            else:
                # Real-time output
                result = subprocess.run(
                    cmd,
                    timeout=timeout,
                    stdin=subprocess.DEVNULL if sys.platform == "win32" else None,
                )
                return ProcessOutput(returncode=result.returncode)
                
        except subprocess.TimeoutExpired:
            self._print_error(f"Process timeout after {timeout} seconds")
            return ProcessOutput(
                stderr=f"Timeout after {timeout}s",
                returncode=-1,
            )
        except Exception as e:
            self._print_error(str(e))
            return ProcessOutput(
                stderr=str(e),
                returncode=-1,
            )

    def run_with_progress(
        self,
        cmd: List[str],
        task_name: str = "",
        progress_callback: Optional[Callable[[str], None]] = None,
        timeout: Optional[float] = None,
    ) -> int:
        """
        Run a subprocess with real-time output processing.
        
        Args:
            cmd: Command and arguments
            task_name: Human-readable task name
            progress_callback: Callback for each output line
            timeout: Process timeout
            
        Returns:
            Return code
        """
        if task_name:
            self._print_task_header(task_name)
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                stdin=subprocess.DEVNULL,
            )
            
            # Read and process output line by line
            for line in iter(process.stdout.readline, ""):
                if line:
                    if progress_callback:
                        progress_callback(line.rstrip("\n\r"))
                    else:
                        print(line.rstrip("\n\r"))
            
            returncode = process.wait(timeout=timeout)
            
            if returncode == 0:
                self._print_success(f"Task completed successfully")
            else:
                self._print_error(f"Task failed with code {returncode}")
            
            return returncode
            
        except subprocess.TimeoutExpired:
            process.kill()
            self._print_error(f"Process timeout after {timeout} seconds")
            return -1
        except Exception as e:
            self._print_error(f"Process error: {e}")
            return -1

    @staticmethod
    def _print_task_header(task_name: str):
        """Print formatted task header."""
        border = "=" * 70
        print(f"\n{border}")
        print(f"  ▶  {task_name}")
        print(f"{border}\n")

    @staticmethod
    def _print_success(msg: str):
        """Print success message."""
        print(f"\n✓ {msg}\n")

    @staticmethod
    def _print_error(msg: str):
        """Print error message."""
        print(f"\n✗ Hata: {msg}\n", file=sys.stderr)

    @staticmethod
    def _print_info(msg: str):
        """Print info message."""
        print(f"ℹ {msg}")


# Global instance
_terminal_manager = None


def get_terminal_manager() -> TerminalManager:
    """Get or create global terminal manager."""
    global _terminal_manager
    if _terminal_manager is None:
        _terminal_manager = TerminalManager()
    return _terminal_manager


class OutputFormatter:
    """Format output messages cleanly."""

    @staticmethod
    def section(title: str):
        """Print section header."""
        print(f"\n{'='*70}\n  {title}\n{'='*70}\n")

    @staticmethod
    def subsection(title: str):
        """Print subsection header."""
        print(f"\n  └─ {title}")

    @staticmethod
    def item(text: str, level: int = 0):
        """Print list item."""
        indent = "    " * level
        print(f"{indent}• {text}")

    @staticmethod
    def success(text: str):
        """Print success message."""
        print(f"\n✓ {text}\n")

    @staticmethod
    def error(text: str):
        """Print error message."""
        print(f"\n✗ {text}\n", file=sys.stderr)

    @staticmethod
    def warning(text: str):
        """Print warning message."""
        print(f"\n⚠ {text}\n")

    @staticmethod
    def progress_bar(current: int, total: int, width: int = 40):
        """Print progress bar."""
        if total == 0:
            percent = 0
        else:
            percent = current / total
        
        filled = int(width * percent)
        bar = "█" * filled + "░" * (width - filled)
        print(f"\r[{bar}] {percent*100:.1f}%", end="", flush=True)
