#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Home Screen - Welcome/Resume screen.
"""

from pathlib import Path
import json

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Button, Footer
from textual.containers import Container, Vertical, Horizontal

BANNER = """
╭──────────────────────────────────────────────────────────────╮
│                    🎬 VIDEO RENDERER v2.0                    │
│              Ubuntu • FFmpeg • Textual TUI                   │
╰──────────────────────────────────────────────────────────────╯
"""


class HomeScreen(Screen):
    """Home screen with welcome message and resume option."""

    BINDINGS = [
        ("n", "new_render", "Yeni Render"),
        ("b", "batch_mode", "Batch Modu"),
        ("r", "resume", "Devam Et"),
        ("q", "quit", "Cikis"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_data = None
        self._check_session()

    def _check_session(self):
        """Check for existing session."""
        session_path = Path.cwd() / "tmp" / "last_session.json"
        if session_path.exists():
            try:
                self.session_data = json.loads(session_path.read_text(encoding="utf-8"))
            except Exception:
                self.session_data = None

    def compose(self) -> ComposeResult:
        with Container(classes="main-wrapper"):
            yield Container(
                Static(BANNER, classes="banner-text"),
                Static(f"📁 {Path.cwd().as_posix()}", classes="subtitle"),
                classes="banner",
            )

            with Vertical(classes="center-container"):
                with Container(classes="panel"):
                    if self.session_data:
                        yield Static("Session Bulundu", classes="panel-title success-text")
                        yield Static(
                            f"📅 {self.session_data.get('ts', 'Bilinmiyor')}", classes="info-text"
                        )
                        yield Static(
                            f"🎬 {Path(self.session_data.get('out', '')).name}", classes="subtitle"
                        )
                        yield Static("")

                        with Horizontal(classes="action-bar"):
                            yield Button("▶ Devam Et", id="resume", classes="-primary")
                            yield Button("🆕 Yeni Render", id="new", classes="-secondary")
                            yield Button("📦 Batch", id="batch", classes="-secondary")
                            yield Button("🚪 Cikis", id="quit", classes="-error")
                    else:
                        yield Static("Video Renderer'a Hos Geldiniz", classes="panel-title")
                        yield Static(
                            "Intro + Loop video birlestirme ve ses miksaji", classes="subtitle"
                        )
                        yield Static("")

                        with Horizontal(classes="action-bar"):
                            yield Button("🆕 Yeni Render", id="new", classes="-primary")
                            yield Button("📦 Batch Modu", id="batch", classes="-secondary")
                            yield Button("🚪 Cikis", id="quit", classes="-secondary")

        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "new":
            self.app.push_screen("video_select")
        elif event.button.id == "batch":
            self.app.push_screen("batch")
        elif event.button.id == "resume":
            if self.session_data:
                self.app.session = self.session_data
                self.app.push_screen("render")
        elif event.button.id == "quit":
            self.app.exit()

    def action_new_render(self) -> None:
        """Start new render."""
        self.app.push_screen("video_select")

    def action_batch_mode(self) -> None:
        """Open batch mode."""
        self.app.push_screen("batch")

    def action_resume(self) -> None:
        """Resume from session."""
        if self.session_data:
            self.app.session = self.session_data
            self.app.push_screen("render")

    def action_quit(self) -> None:
        """Exit app."""
        self.app.exit()
