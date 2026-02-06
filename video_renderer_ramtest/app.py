#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video Renderer TUI Application.

Main Textual application for video rendering.
"""

from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

from textual.app import App
from textual.binding import Binding

from .screens import (
    HomeScreen,
    VideoSelectScreen,
    AudioSelectScreen,
    SettingsScreen,
    RenderScreen,
    CompleteScreen,
    BatchScreen,
    SmartBatchScreen,
)
from .ffmpeg import VideoInfo
from config import CodecConfig


class VideoRendererApp(App):
    """Main Video Renderer TUI Application."""
    
    TITLE = "Video Renderer v2.0"
    SUB_TITLE = "FFmpeg Video Processing"
    
    CSS_PATH = "styles.tcss"
    
    BINDINGS = [
        Binding("ctrl+q", "quit", "Cikis", show=True),
        Binding("ctrl+c", "quit", "Cikis", show=False),
    ]
    
    SCREENS = {
        "home": HomeScreen,
        "video_select": VideoSelectScreen,
        "audio_select": AudioSelectScreen,
        "settings": SettingsScreen,
        "render": RenderScreen,
        "complete": CompleteScreen,
        "batch": BatchScreen,
        "smart_batch": SmartBatchScreen,
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # State variables
        self.intro_path: Optional[Path] = None
        self.intro_info: Optional[VideoInfo] = None
        self.loop_path: Optional[Path] = None
        self.loop_info: Optional[VideoInfo] = None
        self.single_video_path: Optional[Path] = None
        self.single_video_info: Optional[VideoInfo] = None
        self.render_mode: str = "intro_loop"  # intro_loop or single
        
        self.chosen_tracks: List[Path] = []
        self.chosen_bgs: List[Tuple[Path, float]] = []
        
        self.codec_family: str = "av1"
        self.codec_config: Optional[CodecConfig] = None
        self.duration_str: str = "9:00:00"
        self.total_seconds: int = 32400
        self.out_path: Optional[Path] = None
        
        self.session: Optional[Dict[str, Any]] = None
        self.render_result: Optional[Dict[str, Any]] = None
        
        self.render_result: Optional[Dict[str, Any]] = None
        
        # Batch mode
        from .batch import BatchQueue
        self.queue = BatchQueue()
        self.batch_job_id: Optional[int] = None
    
    def on_mount(self) -> None:
        """Called when app is mounted."""
        self.push_screen("home")
    
    def action_quit(self) -> None:
        """Quit the application."""
        self.exit()


def run_tui() -> int:
    """Run the TUI application."""
    app = VideoRendererApp()
    app.run()
    return 0


if __name__ == "__main__":
    run_tui()
