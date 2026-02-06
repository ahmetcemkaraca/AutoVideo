#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audio Selection Screen - Select music tracks and backgrounds.
"""

from pathlib import Path
from typing import List, Set

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Button, Footer, DataTable, Input, Label
from textual.containers import Container, Vertical, Horizontal

from ..ffmpeg import get_duration
from ..audio import is_background_file, parse_background_gain_db


class AudioSelectScreen(Screen):
    """Screen for selecting music tracks and background audio."""

    BINDINGS = [
        ("escape", "go_back", "Geri"),
        ("space", "toggle_selection", "Sec/Kaldir"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tracks: List[Path] = []
        self.backgrounds: List[Path] = []
        self.selected_tracks: Set[int] = set()
        self.selected_bgs: Set[int] = set()
        self.bg_gains: dict = {}  # bg index -> gain in dB
        self.current_table = "tracks"

    def compose(self) -> ComposeResult:
        yield Container(
            Static("🎵 Muzik Secimi", classes="title"),
            Static("Track ve background ses dosyalarini secin", classes="subtitle"),
            classes="container",
        )

        with Horizontal():
            with Container(classes="panel"):
                yield Static("🎼 Muzik Track'leri (Space ile sec)", classes="panel-title")
                yield DataTable(id="tracks_table")
                yield Static("Secilen: 0", id="tracks_count", classes="info-text")

            with Container(classes="panel"):
                yield Static("🔊 Background Sesler (Opsiyonel)", classes="panel-title")
                yield DataTable(id="bgs_table")
                yield Static("Secilen: 0", id="bgs_count", classes="info-text")

        with Horizontal(classes="action-bar"):
            yield Button("← Geri", id="back", classes="-secondary")
            yield Button("Devam →", id="next", classes="-primary", disabled=True)

        yield Footer()

    def on_mount(self) -> None:
        """Called when screen is mounted."""
        self._scan_audio()
        self._update_tables()

    def _scan_audio(self) -> None:
        """Scan for audio files."""
        music_dir = Path.cwd() / "music"
        if not music_dir.exists():
            return

        audio_extensions = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"}

        self.tracks.clear()
        self.backgrounds.clear()
        self.bg_gains.clear()

        for f in sorted(music_dir.iterdir()):
            if f.is_file() and f.suffix.lower() in audio_extensions:
                if is_background_file(f):
                    self.backgrounds.append(f)
                    # Parse gain from filename immediately
                    gain = parse_background_gain_db(f)
                    if gain != 0:
                        self.bg_gains[len(self.backgrounds) - 1] = gain
                    else:
                        self.bg_gains[len(self.backgrounds) - 1] = -15  # default
                else:
                    self.tracks.append(f)

    def _update_tables(self) -> None:
        """Update both tables."""
        # Tracks table
        tracks_table = self.query_one("#tracks_table", DataTable)
        tracks_table.clear(columns=True)
        tracks_table.add_columns("✓", "#", "Dosya", "Sure")

        for i, track in enumerate(self.tracks, 1):
            try:
                dur = get_duration(track)
                dur_str = f"{int(dur//60):02d}:{int(dur%60):02d}"
            except:
                dur_str = "--:--"

            selected = "✓" if i - 1 in self.selected_tracks else " "
            tracks_table.add_row(selected, str(i), track.name, dur_str)

        # Backgrounds table
        bgs_table = self.query_one("#bgs_table", DataTable)
        bgs_table.clear(columns=True)
        bgs_table.add_columns("✓", "#", "Dosya", "dB")

        for i, bg in enumerate(self.backgrounds, 1):
            selected = "✓" if i - 1 in self.selected_bgs else " "
            gain = self.bg_gains.get(i - 1, -15)
            # Use full filename for clearer identification
            bgs_table.add_row(selected, str(i), bg.name, f"{gain:.1f}")

    def _toggle_track(self, index: int) -> None:
        """Toggle track selection."""
        if index in self.selected_tracks:
            self.selected_tracks.remove(index)
        else:
            self.selected_tracks.add(index)

        self._update_selection_visuals("tracks_table", index)
        self._update_counts()
        self._check_can_proceed()

    def _toggle_bg(self, index: int) -> None:
        """Toggle background selection."""
        if index in self.selected_bgs:
            self.selected_bgs.remove(index)
        else:
            self.selected_bgs.add(index)
            # Gain is already set during scanning

        self._update_selection_visuals("bgs_table", index)
        self._update_counts()

    def _update_selection_visuals(self, table_id: str, row_index: int):
        """Optimized visual update for single row toggle."""
        table = self.query_one(f"#{table_id}", DataTable)
        # Re-render everything slightly cheaper than re-calculating whole table is fine for now
        # But actually let's just re-call update tables to be safe corresponding to logic
        self._update_tables()

    def _update_counts(self) -> None:
        """Update selection counts."""
        self.query_one("#tracks_count", Static).update(f"Secilen: {len(self.selected_tracks)}")
        self.query_one("#bgs_count", Static).update(f"Secilen: {len(self.selected_bgs)}")

    def _check_can_proceed(self) -> None:
        """Check if we can proceed."""
        btn = self.query_one("#next", Button)
        btn.disabled = len(self.selected_tracks) == 0

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "next":
            # Store selections in app
            self.app.chosen_tracks = [self.tracks[i] for i in sorted(self.selected_tracks)]
            self.app.chosen_bgs = [
                (self.backgrounds[i], self.bg_gains.get(i, -15)) for i in sorted(self.selected_bgs)
            ]

            self.app.push_screen("settings")

    def action_go_back(self) -> None:
        """Go back."""
        self.app.pop_screen()

    def action_toggle_selection(self) -> None:
        """Toggle current selection."""
        # Find focused table and toggle
        try:
            tracks_table = self.query_one("#tracks_table", DataTable)
            if tracks_table.has_focus and tracks_table.cursor_row is not None:
                self._toggle_track(tracks_table.cursor_row)
                return
        except:
            pass

        try:
            bgs_table = self.query_one("#bgs_table", DataTable)
            if bgs_table.has_focus and bgs_table.cursor_row is not None:
                self._toggle_bg(bgs_table.cursor_row)
        except:
            pass
