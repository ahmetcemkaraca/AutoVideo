#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video Selection Screen - Select intro and loop videos.
"""

from pathlib import Path
from typing import List, Tuple

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Button, Footer, DataTable, Label
from textual.containers import Container, Vertical, Horizontal

from ..ffmpeg import probe_video, VideoInfo


class VideoSelectScreen(Screen):
    """Screen for selecting intro and loop videos."""
    
    BINDINGS = [
        ("escape", "go_back", "Geri"),
        ("enter", "confirm", "Onayla"),
    ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.videos: List[Tuple[Path, VideoInfo]] = []
        self.intro_index = -1
        self.loop_index = -1
        self.selection_phase = "intro"  # intro or loop
    
    def compose(self) -> ComposeResult:
        yield Container(
            Static("🎬 Video Secimi", classes="title"),
            Static("Once INTRO, sonra LOOP video secin (veya tek video modu)", classes="subtitle"),
            classes="container",
        )
        
        with Container(classes="panel"):
            yield Static("", id="selection_label", classes="info-text")
            yield DataTable(id="video_table")
        
        with Container(classes="panel"):
            yield Static("Secilen Videolar", classes="panel-title")
            yield Static("Intro: -", id="intro_label")
            yield Static("Loop: -", id="loop_label")
        
        with Horizontal(classes="action-bar"):
            yield Button("← Geri", id="back", classes="-secondary")
            yield Button("Tek Video →", id="single", classes="-secondary")
            yield Button("Devam →", id="next", classes="-primary", disabled=True)
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Called when screen is mounted."""
        self._scan_videos()
        self._update_table()
        self._update_selection_label()
    
    def _scan_videos(self) -> None:
        """Scan for video files."""
        base = Path.cwd()
        video_extensions = {".mp4", ".mkv", ".avi", ".mov", ".webm"}
        
        self.videos = []
        for f in sorted(base.iterdir()):
            if f.is_file() and f.suffix.lower() in video_extensions:
                try:
                    info = probe_video(f)
                    self.videos.append((f, info))
                except Exception:
                    pass
    
    def _update_table(self) -> None:
        """Update the video table."""
        table = self.query_one("#video_table", DataTable)
        table.clear(columns=True)
        
        table.add_columns("#", "Dosya", "Codec", "Cozunurluk", "Sure")
        
        for i, (path, info) in enumerate(self.videos, 1):
            duration_str = self._format_duration(info.duration)
            res = f"{info.width}x{info.height}"
            codec = info.codec.upper()
            
            table.add_row(str(i), path.name, codec, res, duration_str)
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration as MM:SS."""
        minutes, secs = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"
    
    def _update_selection_label(self) -> None:
        """Update the current selection instruction."""
        label = self.query_one("#selection_label", Static)
        if self.selection_phase == "intro":
            label.update("👆 INTRO video secin (Enter ile onayla) | Tek video icin alttan 'Tek Video' secin")
        else:
            label.update("👆 LOOP video secin (Enter ile onayla)")
    
    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection."""
        index = event.cursor_row
        
        if self.selection_phase == "intro":
            self.intro_index = index
            self._update_intro_label()
            self.selection_phase = "loop"
            self._update_selection_label()
        else:
            if index == self.intro_index:
                self.notify("Ayni video hem intro hem loop olamaz!", severity="warning")
                return
            
            self.loop_index = index
            self._update_loop_label()
            self._enable_next()
    
    def _update_intro_label(self) -> None:
        """Update intro label."""
        if self.intro_index >= 0 and self.intro_index < len(self.videos):
            name = self.videos[self.intro_index][0].name
            self.query_one("#intro_label", Static).update(f"Intro: ✓ {name}")
    
    def _update_loop_label(self) -> None:
        """Update loop label."""
        if self.loop_index >= 0 and self.loop_index < len(self.videos):
            name = self.videos[self.loop_index][0].name
            self.query_one("#loop_label", Static).update(f"Loop: ✓ {name}")
    
    def _enable_next(self) -> None:
        """Enable next button."""
        btn = self.query_one("#next", Button)
        btn.disabled = False
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "next":
            if self.intro_index >= 0 and self.loop_index >= 0:
                # Store selection in app
                self.app.intro_path = self.videos[self.intro_index][0]
                self.app.intro_info = self.videos[self.intro_index][1]
                self.app.loop_path = self.videos[self.loop_index][0]
                self.app.loop_info = self.videos[self.loop_index][1]
                self.app.single_video_path = None
                self.app.single_video_info = None
                self.app.render_mode = "intro_loop"
                
                self.app.push_screen("audio_select")
        elif event.button.id == "single":
            table = self.query_one("#video_table", DataTable)
            if table.cursor_row is None:
                self.notify("Tek video icin once bir satir secin!", severity="warning")
                return
            idx = table.cursor_row
            if idx < 0 or idx >= len(self.videos):
                self.notify("Gecersiz secim!", severity="warning")
                return
            self.app.single_video_path = self.videos[idx][0]
            self.app.single_video_info = self.videos[idx][1]
            self.app.intro_path = None
            self.app.loop_path = None
            self.app.render_mode = "single"
            self.app.push_screen("audio_select")
    
    def action_go_back(self) -> None:
        """Go back."""
        self.app.pop_screen()
    
    def action_confirm(self) -> None:
        """Confirm current selection."""
        table = self.query_one("#video_table", DataTable)
        if table.cursor_row is not None:
            # Trigger selection
            self.on_data_table_row_selected(
                DataTable.RowSelected(table, table.cursor_row, None)
            )
