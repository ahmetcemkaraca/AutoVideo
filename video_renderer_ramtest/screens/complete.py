#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Complete Screen - Render completion summary.
"""

from pathlib import Path

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Button, Footer
from textual.containers import Container, Vertical, Horizontal


class CompleteScreen(Screen):
    """Screen shown after successful render."""
    
    BINDINGS = [
        ("n", "new_render", "Yeni Render"),
        ("q", "quit", "Cikis"),
    ]
    
    def compose(self) -> ComposeResult:
        result = getattr(self.app, 'render_result', {})
        output_path = result.get('output', Path('output.mp4'))
        duration = result.get('duration', 0)
        
        yield Container(
            Static("🎉 Render Tamamlandi!", classes="title success-text"),
            classes="banner",
        )
        
        with Container(classes="panel"):
            yield Static("📋 Sonuc", classes="panel-title")
            yield Static(f"📁 Dosya: {output_path.name}", classes="info-text")
            yield Static(f"📂 Konum: {output_path.parent.as_posix()}", classes="subtitle")
            yield Static(f"⏱️ Sure: {self._format_duration(duration)}", classes="info-text")
            
            if output_path.exists():
                size_mb = output_path.stat().st_size / (1024 * 1024)
                yield Static(f"💾 Boyut: {size_mb:.1f} MB", classes="info-text")
        
        with Horizontal(classes="action-bar"):
            yield Button("🆕 Yeni Render", id="new", classes="-primary")
            yield Button("🚪 Cikis", id="quit", classes="-secondary")
        
        yield Footer()
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration."""
        minutes, secs = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "new":
            # Clear session and start fresh
            session_path = Path.cwd() / "tmp" / "last_session.json"
            session_path.unlink(missing_ok=True)
            
            # Clear app state
            for attr in ['intro_path', 'loop_path', 'single_video_path', 'single_video_info',
                        'chosen_tracks', 'chosen_bgs', 'codec_family', 'codec_config',
                        'out_path', 'session', 'render_result', 'render_mode']:
                if hasattr(self.app, attr):
                    delattr(self.app, attr)
            
            # Go to video select
            self.app.switch_screen("video_select")
        
        elif event.button.id == "quit":
            self.app.exit()
    
    def action_new_render(self) -> None:
        """Start new render."""
        self.on_button_pressed(Button.Pressed(self.query_one("#new", Button)))
    
    def action_quit(self) -> None:
        """Exit."""
        self.app.exit()
