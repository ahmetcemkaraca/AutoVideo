#!/usr/bin/env python3
"""
Mode Selection Screen - choose render mode before all other TUI steps.
"""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Static


class ModeSelectScreen(Screen):
    """Startup screen to choose normal or ramdisk mode."""

    BINDINGS = [
        ("1", "select_standard", "Normal"),
        ("2", "select_ramdisk", "RAM Disk"),
        ("q", "quit", "Cikis"),
    ]

    def compose(self) -> ComposeResult:
        with Container(classes="main-wrapper"), Vertical(classes="center-container"):
            with Container(classes="panel"):
                yield Static("Calisma Modu", classes="panel-title")
                yield Static("Render oncesi modu secin: Normal veya RAM Disk.", classes="subtitle")
                yield Static("")

                with Horizontal(classes="action-bar"):
                    yield Button("1) 🖥️ Normal", id="standard", classes="-primary")
                    yield Button("2) ⚡ RAM Disk", id="ramdisk", classes="-secondary")
                    yield Button("🚪 Cikis", id="quit", classes="-error")

        yield Footer()

    def _go_home(self):
        mode_suffix = {
            "standard": "",
            "ramtest": " [RAM]",
            "ramdisk": " [RAMDisk]",
            "high_vram": " [HighVRAM]",
        }.get(self.app.mode, "")
        self.app.SUB_TITLE = f"FFmpeg Video Processing{mode_suffix}"
        self.app.switch_screen("home")

    def _select_mode(self, mode: str):
        self.app.set_mode(mode)
        self._go_home()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "standard":
            self._select_mode("standard")
        elif event.button.id == "ramdisk":
            self._select_mode("ramdisk")
        elif event.button.id == "quit":
            self.app.exit()

    def action_select_standard(self) -> None:
        self._select_mode("standard")

    def action_select_ramdisk(self) -> None:
        self._select_mode("ramdisk")

    def action_quit(self) -> None:
        self.app.exit()
