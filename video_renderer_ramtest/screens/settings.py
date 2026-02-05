#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Settings Screen - Codec, duration, output settings.
"""

from pathlib import Path
from typing import Dict

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Button, Footer, Input, RadioSet, RadioButton, Label
from textual.containers import Container, Vertical, Horizontal

from ..config import detect_available_encoders, get_best_encoder
from ..ffmpeg import get_duration


DURATION_PRESETS = {
    "3 saat": "3:00:00",
    "6 saat": "6:00:00",
    "9 saat": "9:00:00",
    "12 saat": "12:00:00",
    "Rastgele (8-10s)": "random_8_10",
}


class SettingsScreen(Screen):
    """Screen for codec, duration and output settings."""
    
    BINDINGS = [
        ("escape", "go_back", "Geri"),
    ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.available_codecs: Dict[str, bool] = {}
        self.selected_codec = "av1"
        self.duration_str = "9:00:00"
        self.output_name = ""
        self.enable_upload = False
        self.drive_folder_id = ""

    
    def compose(self) -> ComposeResult:
        yield Container(
            Static("⚙️ Ayarlar", classes="title"),
            Static("Codec, sure ve cikti ayarlarini yapin", classes="subtitle"),
            classes="container",
        )
        
        with Horizontal():
            # Codec selection
            with Container(classes="panel"):
                yield Static("🎞️ Video Codec", classes="panel-title")
                yield Static("", id="codec_info", classes="subtitle")
                with RadioSet(id="codec_radio"):
                    yield RadioButton("AV1 (Kaliteli, kucuk boyut)", id="av1", value=True)
                    yield RadioButton("H.265/HEVC (Dengeli)", id="h265")
                    yield RadioButton("H.264/AVC (Uyumlu)", id="h264")
            
            # Duration
            with Container(classes="panel"):
                yield Static("⏱️ Sure", classes="panel-title")
                with RadioSet(id="duration_radio"):
                    yield RadioButton("3 saat", id="dur_3")
                    yield RadioButton("6 saat", id="dur_6")
                    yield RadioButton("9 saat", id="dur_9", value=True)
                    yield RadioButton("12 saat", id="dur_12")
                    yield RadioButton("Rastgele (8-10 saat)", id="dur_random")
                yield Static("Veya ozel sure (HH:MM:SS):", classes="subtitle")
                yield Input(placeholder="9:00:00", id="custom_duration")
        
        # Drive Upload Settings
        with Container(classes="panel"):
            yield Static("☁️ Google Drive Upload", classes="panel-title")
            yield Horizontal(
                Button("Upload Aktif Et", id="toggle_upload", variant="error"),
                Label("Devre Disi", id="upload_status_label", classes="status-label"),
                classes="upload-row"
            )
            yield Input(placeholder="Drive Folder ID (Opsiyonel)", id="drive_folder_id", classes="hidden")
            yield Static("Varsayilan klasor ID'si. Bos birakilirsa root'a yuklenir.", id="drive_hint", classes="subtitle hidden")

        # Ramtest Options
        with Container(classes="panel"):
            yield Static("🧪 Ramtest Secenekleri", classes="panel-title")
            yield Checkbox("Video Renderer Paketini Kullan (Ana Surum)", id="use_main_renderer", value=False)
            yield Static("Render islemi icin 'video_renderer' klasorundeki kodlari kullanir.", classes="subtitle")

        # Output filename
        with Container(classes="panel"):
            yield Static("💾 Cikti Dosyasi", classes="panel-title")
            yield Input(placeholder="output.mp4", id="output_name")
            yield Static("Bos birakilirsa otomatik isim verilir", classes="subtitle")
        
        # Summary
        with Container(classes="panel"):
            yield Static("📋 Ozet", classes="panel-title")
            yield Static("", id="summary_intro")
            yield Static("", id="summary_loop")
            yield Static("", id="summary_codec")
            yield Static("", id="summary_duration")
            yield Static("", id="summary_tracks")
            yield Static("", id="summary_bgs")
            yield Static("", id="summary_upload")
        
        with Horizontal(classes="action-bar"):
            yield Button("← Geri", id="back", classes="-secondary")
            yield Button("🚀 Render Baslat", id="start", classes="-primary")
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Called when screen is mounted."""
        self._detect_codecs()
        self._update_summary()
        self._generate_default_filename()
        
        # Restore checkbox if set
        if getattr(self.app, "use_main_renderer", False):
            self.query_one("#use_main_renderer", Checkbox).value = True
    
    def _detect_codecs(self) -> None:
        """Detect available codecs."""
        self.available_codecs = detect_available_encoders()
        
        info_parts = []
        for name, available in self.available_codecs.items():
            if available:
                info_parts.append(f"✓ {name}")
        
        if info_parts:
            self.query_one("#codec_info", Static).update(" | ".join(info_parts))
    
    def _update_summary(self) -> None:
        """Update the summary panel."""
        app = self.app

        if getattr(app, "render_mode", "intro_loop") == "single" and getattr(app, "single_video_path", None):
            self.query_one("#summary_intro", Static).update(
                f"Video: {app.single_video_path.name}"
            )
            self.query_one("#summary_loop", Static).update("")
        else:
            if hasattr(app, 'intro_path') and app.intro_path:
                self.query_one("#summary_intro", Static).update(
                    f"Intro: {app.intro_path.name}"
                )
            if hasattr(app, 'loop_path') and app.loop_path:
                self.query_one("#summary_loop", Static).update(
                    f"Loop: {app.loop_path.name}"
                )
        
        self.query_one("#summary_codec", Static).update(
            f"Codec: {self.selected_codec.upper()}"
        )
        
        if getattr(app, "render_mode", "intro_loop") == "single" and getattr(app, "single_video_path", None):
            try:
                video_seconds = int(get_duration(app.single_video_path))
                h = video_seconds // 3600
                m = (video_seconds % 3600) // 60
                s = video_seconds % 60
                video_dur = f"{h:02d}:{m:02d}:{s:02d}"
            except Exception:
                video_dur = self.duration_str
            self.query_one("#summary_duration", Static).update(
                f"Sure: {video_dur} (Video suresi)"
            )
        else:
            self.query_one("#summary_duration", Static).update(
                f"Sure: {self.duration_str}"
            )
        
        if hasattr(app, 'chosen_tracks'):
            self.query_one("#summary_tracks", Static).update(
                f"Track: {len(app.chosen_tracks)} adet"
            )
        
        if hasattr(app, 'chosen_bgs'):
            self.query_one("#summary_bgs", Static).update(
                f"BG: {len(app.chosen_bgs)} adet"
            )

        upload_text = "Upload: Kapali"
        if self.enable_upload:
            upload_text = f"Upload: Aktif ({self.drive_folder_id or 'Root'})"
        self.query_one("#summary_upload", Static).update(upload_text)
    
    def _generate_default_filename(self) -> None:
        """Generate default output filename."""
        import time
        
        app = self.app
        if getattr(app, "render_mode", "intro_loop") == "single" and getattr(app, "single_video_path", None):
            base_name = app.single_video_path.stem
        elif hasattr(app, 'intro_path') and app.intro_path:
            base_name = app.intro_path.stem
        else:
            base_name = "output"
        timestamp = time.strftime("%Y%m%d")
        self.output_name = f"{base_name}_{timestamp}.mp4"
        self.query_one("#output_name", Input).value = self.output_name
    
    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """Handle radio selection changes."""
        radio_id = event.radio_set.id
        
        if radio_id == "codec_radio":
            pressed = event.pressed
            if pressed:
                self.selected_codec = pressed.id
                self._update_summary()
        
        elif radio_id == "duration_radio":
            pressed = event.pressed
            if pressed:
                dur_map = {
                    "dur_3": "3:00:00",
                    "dur_6": "6:00:00",
                    "dur_9": "9:00:00",
                    "dur_12": "12:00:00",
                    "dur_random": "random_8_10",
                }
                self.duration_str = dur_map.get(pressed.id, "9:00:00")
                self._update_summary()
    
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes."""
        if event.input.id == "custom_duration":
            if event.value:
                self.duration_str = event.value
                self._update_summary()
        elif event.input.id == "output_name":
            self.output_name = event.value
        elif event.input.id == "drive_folder_id":
            self.drive_folder_id = event.value
            self._update_summary()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "start":
            self._start_render()
        elif event.button.id == "toggle_upload":
            self._toggle_upload()

    def _toggle_upload(self) -> None:
        """Toggle upload state."""
        self.enable_upload = not self.enable_upload
        
        btn = self.query_one("#toggle_upload", Button)
        lbl = self.query_one("#upload_status_label", Label)
        inp = self.query_one("#drive_folder_id", Input)
        hint = self.query_one("#drive_hint", Static)
        
        if self.enable_upload:
            btn.variant = "success"
            btn.label = "Upload Devre Disi Birak"
            lbl.update("AKTIF")
            lbl.add_class("-active")
            inp.remove_class("hidden")
            hint.remove_class("hidden")
        else:
            btn.variant = "error"
            btn.label = "Upload Aktif Et"
            lbl.update("Devre Disi")
            lbl.remove_class("-active")
            inp.add_class("hidden")
            hint.add_class("hidden")
        
        self._update_summary()
    
    def _start_render(self) -> None:
        """Start the render process."""
        # Parse duration (or use video duration for single mode)
        if getattr(self.app, "render_mode", "intro_loop") == "single" and getattr(self.app, "single_video_path", None):
            try:
                total_seconds = int(get_duration(self.app.single_video_path))
            except Exception:
                total_seconds = 0
        else:
            total_seconds = self._parse_duration(self.duration_str)
        if total_seconds <= 0:
            self.notify("Gecersiz sure!", severity="error")
            return
        
        # Get codec config
        codec_config = get_best_encoder(self.selected_codec)
        
        # Determine output path
        if not self.output_name:
            self._generate_default_filename()
        
        out_path = Path.cwd() / self.output_name
        
        # Store all settings in app
        self.app.codec_family = self.selected_codec
        self.app.codec_config = codec_config
        if getattr(self.app, "render_mode", "intro_loop") == "single" and getattr(self.app, "single_video_path", None):
            h = total_seconds // 3600
            m = (total_seconds % 3600) // 60
            s = total_seconds % 60
            self.duration_str = f"{h:02d}:{m:02d}:{s:02d}"
        self.app.duration_str = self.duration_str
        self.app.total_seconds = total_seconds
        self.app.out_path = out_path
        
        # Save upload settings
        self.app.enable_upload = self.enable_upload
        self.app.drive_folder_id = self.drive_folder_id
        
        # Save ramtest options
        try:
            self.app.use_main_renderer = self.query_one("#use_main_renderer", Checkbox).value
        except:
            self.app.use_main_renderer = False
        
        # Go to render screen
        self.app.push_screen("render")
            
    def _parse_duration(self, dur_str: str) -> int:
        """Parse duration string to seconds."""
        if dur_str == "random_8_10":
            import random
            # 8 hours = 28800, 10 hours = 36000
            return random.randint(28800, 36000)
            
        try:
            parts = dur_str.strip().split(":")
            if len(parts) == 3:
                h, m, s = map(int, parts)
                return h * 3600 + m * 60 + s
            elif len(parts) == 2:
                m, s = map(int, parts)
                return m * 60 + s
            else:
                return int(parts[0]) * 3600
        except Exception:
            return 0
    
    def action_go_back(self) -> None:
        """Go back."""
        self.app.pop_screen()
