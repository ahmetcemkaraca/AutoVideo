#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Settings Screen - Codec, duration, output settings with mode-specific options.
"""

from pathlib import Path
from typing import Dict, Literal

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Button, Footer, Input, RadioSet, RadioButton, Label, Checkbox
from textual.containers import Container, Vertical, Horizontal

from config import detect_available_encoders, get_best_encoder, get_render_config
from ..ffmpeg import get_duration

DURATION_PRESETS = {
    "3 saat": "3:00:00",
    "6 saat": "6:00:00",
    "9 saat": "9:00:00",
    "12 saat": "12:00:00",
    "Rastgele (8-10s)": "random_8_10",
}


class SettingsScreen(Screen):
    """Screen for codec, duration and output settings with mode awareness."""

    BINDINGS = [
        ("escape", "go_back", "Geri"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.available_codecs: Dict[str, bool] = {}
        self.selected_codec = "av1"
        self.duration_str = "9:00:00"
        self.output_name = ""
        self.video_bitrate = ""  # Custom bitrate (e.g. 5000k)
        self.enable_upload = False
        self.drive_folder_id = ""

        # Mode detection
        self.app_mode = getattr(self.app, "mode", "standard")
        self.mode_config = getattr(self.app, "mode_config", None)
        
        # Batch Mode Check
        self.is_batch = getattr(self.app, "batch_job_id", None) is not None

    def compose(self) -> ComposeResult:
        # Mode indicator in title
        mode_suffix = {
            "standard": "",
            "ramtest": " [RAM]",
            "ramdisk": " [RAMDisk]",
            "high_vram": " [HighVRAM]",
        }.get(self.app_mode, "")

        yield Container(
            Static(f"⚙️ Ayarlar{mode_suffix}", classes="title"),
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
            
            # Duration & Bitrate
            with Container(classes="panel"):
                yield Static("⏱️ Sure & Kalite", classes="panel-title")
                with RadioSet(id="duration_radio"):
                    yield RadioButton("3 saat", id="dur_3")
                    yield RadioButton("6 saat", id="dur_6")
                    yield RadioButton("9 saat", id="dur_9", value=True)
                    yield RadioButton("12 saat", id="dur_12")
                    yield RadioButton("Rastgele (8-10 saat)", id="dur_random")
                
                yield Static("Ozel Sure (HH:MM:SS):", classes="subtitle")
                yield Input(placeholder="9:00:00", id="custom_duration")
                
                yield Static("Video Bitrate (Bos=Oto):", classes="subtitle")
                yield Input(placeholder="Orn: 5000k, 5M, 8M...", id="video_bitrate")

        # Mode-specific options
        if self.app_mode in ["ramtest", "ramdisk"]:
            with Container(classes="panel mode-panel"):
                yield Static("💾 RAM Optimizasyon", classes="panel-title")

                # RAM Disk option (for ramtest mode)
                if self.app_mode == "ramtest" and self.mode_config:
                    yield Checkbox(
                        "RAM Disk Kullan (tmpfs)",
                        value=self.mode_config.use_ramdisk,
                        id="use_ramdisk",
                        classes="mode-option",
                    )
                    yield Static(
                        "Temp dosyalari RAM disk'te saklar (daha hizli, daha az disk I/O)",
                        id="ramdisk_hint",
                        classes="subtitle",
                    )

                # High VRAM option
                if self.app_mode == "ramtest" and self.mode_config:
                    yield Checkbox(
                        "High VRAM Modu (8GB+ GPU)",
                        value=self.mode_config.high_vram,
                        id="high_vram",
                        classes="mode-option",
                    )
                    yield Static(
                        "Yuksek GPU bellek optimizasyonu ( daha iyi encoder performansi)",
                        id="vram_hint",
                        classes="subtitle",
                    )

                # Chunk long videos option
                if self.app_mode == "ramtest" and self.mode_config:
                    yield Checkbox(
                        "Uzun Videolari Parcalara Bol (Chunking)",
                        value=self.mode_config.chunk_long_videos,
                        id="chunk_videos",
                        classes="mode-option",
                    )
                    yield Static(
                        "Bellek dusukse uzun videolari 2 saatlik parcalar halinde isler",
                        id="chunk_hint",
                        classes="subtitle",
                    )

        elif self.app_mode == "high_vram" and self.mode_config:
            with Container(classes="panel mode-panel"):
                yield Static("🎮 High VRAM Ayarlari", classes="panel-title")
                yield Static(
                    f"GPU Bellek Optimizasyonu Aktif ({self.mode_config.high_vram})",
                    id="vram_status",
                    classes="info-text",
                )
                yield Static(
                    "Encoder performansini artirmak icin GPU buffer boyutlari artirildi",
                    id="vram_status_hint",
                    classes="subtitle",
                )

        # Drive Upload Settings
        with Container(classes="panel"):
            yield Static("☁️ Google Drive Upload", classes="panel-title")
            yield Horizontal(
                Button("Upload Aktif Et", id="toggle_upload", variant="error"),
                Label("Devre Disi", id="upload_status_label", classes="status-label"),
                classes="upload-row",
            )
            yield Input(
                placeholder="Drive Folder ID (Opsiyonel)", id="drive_folder_id", classes="hidden"
            )
            yield Static(
                "Varsayilan klasor ID'si. Bos birakilirsa root'a yuklenir.",
                id="drive_hint",
                classes="subtitle hidden",
            )

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
            yield Static("", id="summary_bitrate") 
            yield Static("", id="summary_tracks")
            yield Static("", id="summary_bgs")
            yield Static("", id="summary_upload")
            yield Static("", id="summary_mode")

        with Horizontal(classes="action-bar"):
            yield Button("← Geri", id="back", classes="-secondary")
            label = "💾 Isi Kaydet" if self.is_batch else "🚀 Render Baslat"
            variant = "primary" if self.is_batch else "success"
            yield Button(label, id="start", variant=variant)

        yield Footer()

    def on_mount(self) -> None:
        """Called when screen is mounted."""
        self._detect_codecs()
        self._update_summary()
        self._generate_default_filename()
        self._init_mode_options()

    def _init_mode_options(self) -> None:
        """Initialize mode-specific options from mode_config."""
        if self.mode_config and self.app_mode in ["ramtest", "ramdisk"]:
            try:
                # Set checkbox values from mode_config
                if self.app_mode == "ramtest":
                    if hasattr(self, "query_one"):
                        try:
                            self.query_one("#use_ramdisk", Checkbox).value = (
                                self.mode_config.use_ramdisk
                            )
                            self.query_one("#high_vram", Checkbox).value = (
                                self.mode_config.high_vram
                            )
                            self.query_one("#chunk_videos", Checkbox).value = (
                                self.mode_config.chunk_long_videos
                            )
                        except Exception:
                            pass  # Checkboxes might not exist in all modes
            except Exception:
                pass

    def _detect_codecs(self) -> None:
        """Detect available codecs."""
        self.available_codecs = detect_available_encoders()

        info_parts = []
        for name, available in self.available_codecs.items():
            if available:
                info_parts.append(f"✓ {name}")

        if info_parts:
            try:
                self.query_one("#codec_info", Static).update(" | ".join(info_parts))
            except Exception:
                pass

    def _update_summary(self) -> None:
        """Update the summary panel."""
        app = self.app

        if getattr(app, "render_mode", "intro_loop") == "single" and getattr(
            app, "single_video_path", None
        ):
            try:
                self.query_one("#summary_intro", Static).update(
                    f"Video: {app.single_video_path.name}"
                )
                self.query_one("#summary_loop", Static).update("")
            except Exception:
                pass
        else:
            if hasattr(app, "intro_path") and app.intro_path:
                try:
                    self.query_one("#summary_intro", Static).update(f"Intro: {app.intro_path.name}")
                except Exception:
                    pass
            if hasattr(app, "loop_path") and app.loop_path:
                try:
                    self.query_one("#summary_loop", Static).update(f"Loop: {app.loop_path.name}")
                except Exception:
                    pass

        try:
            self.query_one("#summary_codec", Static).update(f"Codec: {self.selected_codec.upper()}")
        except Exception:
            pass

        if getattr(app, "render_mode", "intro_loop") == "single" and getattr(
            app, "single_video_path", None
        ):
            try:
                video_seconds = int(get_duration(app.single_video_path))
                h = video_seconds // 3600
                m = (video_seconds % 3600) // 60
                s = video_seconds % 60
                video_dur = f"{h:02d}:{m:02d}:{s:02d}"
            except Exception:
                video_dur = self.duration_str
            try:
                self.query_one("#summary_duration", Static).update(
                    f"Sure: {video_dur} (Video suresi)"
                )
            except Exception:
                pass
        else:
            try:
                self.query_one("#summary_duration", Static).update(f"Sure: {self.duration_str}")
            except Exception:
                pass

        # Bitrate Summary
        try:
            bitrate_text = f"Bitrate: {self.video_bitrate}" if self.video_bitrate else "Bitrate: Otomatik (CRF)"
            self.query_one("#summary_bitrate", Static).update(bitrate_text)
        except Exception:
            pass

        if hasattr(app, "chosen_tracks"):
            try:
                self.query_one("#summary_tracks", Static).update(
                    f"Track: {len(app.chosen_tracks)} adet"
                )
            except Exception:
                pass

        if hasattr(app, "chosen_bgs"):
            try:
                self.query_one("#summary_bgs", Static).update(f"BG: {len(app.chosen_bgs)} adet")
            except Exception:
                pass

        upload_text = "Upload: Kapali"
        if self.enable_upload:
            upload_text = f"Upload: Aktif ({self.drive_folder_id or 'Root'})"
        try:
            self.query_one("#summary_upload", Static).update(upload_text)
        except Exception:
            pass

        # Mode info in summary
        mode_text = {
            "standard": "Mod: Standard",
            "ramtest": "Mod: RAM-Optimized",
            "ramdisk": "Mod: RAM Disk",
            "high_vram": "Mod: High VRAM",
        }.get(self.app_mode, f"Mod: {self.app_mode}")
        try:
            self.query_one("#summary_mode", Static).update(mode_text)
        except Exception:
            pass

    def _generate_default_filename(self) -> None:
        """Generate default output filename."""
        import time

        app = self.app
        if getattr(app, "render_mode", "intro_loop") == "single" and getattr(
            app, "single_video_path", None
        ):
            base_name = app.single_video_path.stem
        elif hasattr(app, "intro_path") and app.intro_path:
            base_name = app.intro_path.stem
        else:
            base_name = "output"

        # Add mode suffix to filename
        mode_suffix = {
            "standard": "",
            "ramtest": "_ram",
            "ramdisk": "_ramdisk",
            "high_vram": "_vram",
        }.get(self.app_mode, "")

        timestamp = time.strftime("%Y%m%d")
        self.output_name = f"{base_name}{mode_suffix}_{timestamp}.mp4"
        try:
            self.query_one("#output_name", Input).value = self.output_name
        except Exception:
            pass

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
        elif event.input.id == "video_bitrate":
            self.video_bitrate = event.value
            self._update_summary()
        elif event.input.id == "output_name":
            self.output_name = event.value
        elif event.input.id == "drive_folder_id":
            self.drive_folder_id = event.value
            self._update_summary()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Handle checkbox changes for mode-specific options."""
        if self.mode_config and self.app_mode == "ramtest":
            checkbox_id = event.checkbox.id
            if checkbox_id == "use_ramdisk":
                self.mode_config.use_ramdisk = event.value
            elif checkbox_id == "high_vram":
                self.mode_config.high_vram = event.value
            elif checkbox_id == "chunk_videos":
                self.mode_config.chunk_long_videos = event.value

            # Update app config
            if hasattr(self.app, "ramtest_config"):
                self.app.ramtest_config.use_ramdisk = self.mode_config.use_ramdisk
                self.app.ramtest_config.high_vram = self.mode_config.high_vram
                self.app.ramtest_config.chunk_long_videos = self.mode_config.chunk_long_videos

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
        """Start the render process or save batch job."""
        # Parse duration (or use video duration for single mode)
        if getattr(self.app, "render_mode", "intro_loop") == "single" and getattr(
            self.app, "single_video_path", None
        ):
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

        # --- BATCH MODE ---
        if self.is_batch and hasattr(self.app, "batch_job_id"):
            # Update the queued job instead of starting immediate render
            from ..batch import JobStatus
            
            queue = getattr(self.app, "queue", None)
            if queue:
                # We need to update the job in the queue
                # Since queue returns copies, we should likely update it via a method
                # But typically we access the job directly if it's mutable in memory before saving?
                # The BatchQueue design uses copies. We need to update and save.
                # Actually, the queue.create_job() returned a job copy.
                # We should re-fetch it or assume our local ID is valid.
                
                # Let's simple "add" it or update it. 
                # Since we likely just created it in batch screen and came here,
                # we can probably just update its fields.
                
                # However, BatchQueue interface is a bit strict.
                # We need to use `_lock` or helper. 
                # Let's assume we can get the job, update it, and save?
                # Or better, just queue_job() which saves? 
                # But we need to update fields first.
                
                # Hacky but effective: Directly modify the job in queue._jobs using lock
                # (Since we are inside the app)
                with queue._lock:
                    job = queue._get_job_unsafe(self.app.batch_job_id)
                    if job:
                        job.codec_family = self.selected_codec
                        job.duration_str = self.duration_str
                        job.total_seconds = total_seconds
                        job.output_path = out_path
                        job.video_bitrate = self.video_bitrate if self.video_bitrate else None
                        
                        # Set tracks/bgs from app state
                        job.tracks = getattr(self.app, "chosen_tracks", [])
                        job.backgrounds = getattr(self.app, "chosen_bgs", [])
                        
                        job.upload_enabled = self.enable_upload
                        job.upload_folder_id = self.drive_folder_id
                        
                        # Mark as queued
                        job.status = JobStatus.QUEUED
                        queue._save()
                        
                        self.notify(f"Is #{job.id} kuyruga eklendi!")
            
            # Navigate back to batch screen
            # Stack: Batch -> VideoSelect -> AudioSelect -> Settings
            # Pop 3 times? Or just pop until Batch?
            # Easier: Pop, Pop, Pop
            self.app.pop_screen() # Settings -> Audio
            self.app.pop_screen() # Audio -> Video
            self.app.pop_screen() # Video -> Batch
            return

        # --- IMMEDIATE RENDER MODE ---
        
        # Store all settings in app
        self.app.codec_family = self.selected_codec
        self.app.codec_config = codec_config
        self.app.video_bitrate = self.video_bitrate if self.video_bitrate else None
        
        if getattr(self.app, "render_mode", "intro_loop") == "single" and getattr(
            self.app, "single_video_path", None
        ):
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

        # Create isolated temp context for this render run
        if hasattr(self.app, "start_new_run_context"):
            self.app.start_new_run_context()

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
