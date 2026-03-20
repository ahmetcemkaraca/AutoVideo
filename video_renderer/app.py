#!/usr/bin/env python3
"""
Video Renderer TUI Application.

Main Textual application for video rendering.
Supports multiple render modes: standard, ramtest, ramdisk, high_vram.

Resource Management:
- Uses ResourceManager for process tracking and cleanup
- Graceful shutdown on signals (SIGTERM, SIGINT)
- Automatic temp file cleanup
"""

import os

# Fix: Ensure project root is in Python path for config imports
# This resolves the issue where files import from root `config/` which may not be in Python path
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from textual.app import App
from textual.binding import Binding

from .ffmpeg import VideoInfo
from .screens import (
    AudioSelectScreen,
    BatchScreen,
    CompleteScreen,
    HomeScreen,
    ModeSelectScreen,
    RenderScreen,
    SettingsScreen,
    SmartBatchScreen,
    ValidationScreen,
    VideoSelectScreen,
)

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from config import CodecConfig, RamTestConfig, get_render_config

from .resource_manager import ResourceManager


@dataclass
class RenderModeConfig:
    """Unified render mode configuration."""

    mode: Literal["standard", "ramtest", "ramdisk", "high_vram"] = "standard"
    enabled: bool = False
    use_ramdisk: bool = False
    high_vram: bool = False
    chunk_long_videos: bool = False
    chunk_size_hours: float = 2.0


class VideoRendererApp(App):
    """
    Main Video Renderer TUI Application with Unified Mode Support.

    Features:
    - Unified state management via StateManager (in BatchQueue)
    - Resource tracking and cleanup via ResourceManager
    - Graceful shutdown on termination signals
    - Support for multiple render modes
    """

    TITLE = "Video Renderer v2.0"
    SUB_TITLE = "FFmpeg Video Processing"

    CSS_PATH = "styles.tcss"

    BINDINGS = [
        Binding("ctrl+q", "quit", "Cikis", show=True),
        Binding("ctrl+c", "quit", "Cikis", show=False),
    ]

    SCREENS = {
        "mode_select": ModeSelectScreen,
        "home": HomeScreen,
        "video_select": VideoSelectScreen,
        "audio_select": AudioSelectScreen,
        "settings": SettingsScreen,
        "render": RenderScreen,
        "complete": CompleteScreen,
        "batch": BatchScreen,
        "smart_batch": SmartBatchScreen,
        "validation": ValidationScreen,
    }

    def __init__(
        self,
        mode: Literal["standard", "ramtest", "ramdisk", "high_vram"] = "standard",
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        # Resource Manager for cleanup and graceful shutdown
        self.resource_manager = ResourceManager(enable_signals=True)

        # Unified mode configuration
        self.mode = mode
        self.mode_config = self._init_mode_config(mode)
        self.mode_selected = False

        # Legacy ramtest_mode support (for backward compatibility)
        self.ramtest_mode = mode in ["ramtest", "ramdisk"]
        self.ramtest_config = RamTestConfig(enabled=self.ramtest_mode)

        # State variables
        self.intro_path: Path | None = None
        self.intro_info: VideoInfo | None = None
        self.loop_path: Path | None = None
        self.loop_info: VideoInfo | None = None
        self.single_video_path: Path | None = None
        self.single_video_info: VideoInfo | None = None
        self.render_mode: str = "intro_loop"  # intro_loop or single

        self.chosen_tracks: list[Path] = []
        self.chosen_bgs: list[tuple[Path, float]] = []

        self.codec_family: str = "av1"
        self.codec_config: CodecConfig | None = None
        self.duration_str: str = "9:00:00"
        self.total_seconds: int = 32400
        self.out_path: Path | None = None

        self.session: dict[str, Any] | None = None
        self.render_result: dict[str, Any] | None = None

        # Batch mode (uses StateManager internally)
        from .batch import BatchQueue

        self.queue = BatchQueue()
        self.batch_job_id: int | None = None

        # Drive integration
        self.drive_folder_id: str | None = None
        self.enable_upload: bool = False

        # Validation control
        self.skip_validation: bool = False

        # Session / temp paths (isolated per render run)
        self.base_tmp_dir = Path.cwd() / "tmp"
        self.base_tmp_dir.mkdir(parents=True, exist_ok=True)
        self.runs_root = self.base_tmp_dir / "runs"
        self.runs_root.mkdir(parents=True, exist_ok=True)
        self.session_file = self.base_tmp_dir / "last_session.json"
        self.current_run_id: str | None = None
        self.current_run_tmp_dir: Path = self.base_tmp_dir

        # Mode-specific features
        if mode == "ramtest":
            self._setup_ramtest_mode()

    def start_new_run_context(self) -> Path:
        """Create isolated tmp directory for one render run."""
        run_id = f"{time.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}_{uuid.uuid4().hex[:6]}"
        run_dir = self.runs_root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        self.current_run_id = run_id
        self.current_run_tmp_dir = run_dir
        return run_dir

    def set_mode(self, mode: Literal["standard", "ramtest", "ramdisk", "high_vram"]) -> None:
        """Set active render mode at runtime before render flow starts."""
        self.mode = mode
        self.mode_config = self._init_mode_config(mode)
        self.ramtest_mode = mode in ["ramtest", "ramdisk"]
        self.ramtest_config = RamTestConfig(enabled=self.ramtest_mode)
        self.mode_selected = True

        if mode == "ramtest":
            self._setup_ramtest_mode()

    def _init_mode_config(self, mode: str) -> RenderModeConfig:
        """Initialize mode-specific configuration using factory function."""
        # Get base config from factory
        base_config = get_render_config(mode)

        # Override with runtime detection for ramtest mode
        if mode == "ramtest":
            base_config.enabled = True
            base_config.use_ramdisk = self._check_ramdisk()
            base_config.high_vram = self._check_vram()
            base_config.chunk_long_videos = self._check_ram()
        elif mode in ("ramdisk", "high_vram"):
            base_config.enabled = True

        return base_config

    def _check_vram(self) -> bool:
        """Check if high VRAM is available (8GB+)."""
        try:
            import subprocess

            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                vram_mb = int(result.stdout.strip().split()[0])
                return vram_mb >= 8000  # 8GB+
        except Exception:
            pass
        return False

    def _check_ram(self) -> bool:
        """Check if chunking is needed (less than 16GB RAM)."""
        try:
            import psutil

            return psutil.virtual_memory().total < 16 * 1024**3  # < 16GB
        except Exception:
            return False

    def _check_ramdisk(self) -> bool:
        """Check if RAM disk is available."""
        try:
            from config import get_ramdisk_path

            return get_ramdisk_path() is not None
        except Exception:
            return False

    def _setup_ramtest_mode(self):
        """Setup ramtest-specific features."""
        self.show_memory_info = True
        self.enable_rate_limiting = True

    def on_mount(self) -> None:
        """Called when app is mounted."""
        self.push_screen("mode_select")

    def action_quit(self) -> None:
        """
        Quit the application with proper cleanup.

        ResourceManager handles:
        - Terminating all FFmpeg processes
        - Cleaning up temporary files
        - Invoking custom cleanup callbacks
        """
        # Cleanup ramtest temp files if enabled
        if self.mode_config.use_ramdisk:
            from config import cleanup_ramdisk

            cleanup_ramdisk()

        # ResourceManager cleanup is automatic via atexit and signal handlers
        # But we can call it explicitly here for immediate cleanup
        self.resource_manager.cleanup()

        self.exit()


def run_tui(mode: Literal["standard", "ramtest", "ramdisk", "high_vram"] = "standard") -> int:
    """
    Run the TUI application.

    Args:
        mode: Render mode - standard, ramtest, ramdisk, or high_vram
    """
    app = VideoRendererApp(mode=mode)
    app.run()
    return 0


if __name__ == "__main__":
    run_tui()
