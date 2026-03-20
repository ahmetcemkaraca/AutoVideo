#!/usr/bin/env python3
"""
Smart Batch Screen - Wizard for auto-detecting and configuring batch jobs.
"""

import random
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Button, Checkbox, DataTable, Footer, Input, Label, Select, Static

from ..audio import is_background_file
from ..batch import BatchPair, BatchQueue, JobStatus, SmartBatchDetector, parse_duration


class SmartBatchScreen(Screen):
    """Wizard for smart batch creation."""

    BINDINGS = [
        ("escape", "go_back", "Geri"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.detector = SmartBatchDetector()
        self.pairs: list[BatchPair] = []
        self.selected_indices: set[int] = set()

        # Wizard state
        self.step = 1  # 1: Global Settings, 2: Customization (Loop)
        self.current_pair_idx = 0
        self.customizing_pairs: list[int] = []  # Indices of pairs to customize

        # Settings
        self.global_duration = "9:00:00"
        self.global_codec = "av1"
        self.music_mode = "random"  # random, specific, none
        self.music_tracks: list[Path] = []  # All available tracks
        self.global_selected_tracks: list[Path] = []
        self.global_selected_tracks: list[Path] = []
        self.global_bg_files: list[Path] = []
        self.global_bitrate = ""  # New: Bitrate support

        # Per-project settings (index -> settings dict)
        self.project_settings = {}

    def compose(self) -> ComposeResult:
        yield Container(
            Static("✨ Smart Batch Sihirbazi", classes="title"),
            Static("Otomatik tespit edilen ciftleri siraya ekle", classes="subtitle"),
            classes="container",
        )

        # STEP 1: Global Settings & Selection
        with Container(id="step1_container"), Horizontal():
            # Left: Pairs List
            with Container(classes="panel"):
                yield Static("📂 Tespit Edilen Projeler", classes="panel-title")
                yield DataTable(id="pairs_table")

            # Right: Settings
            with Container(classes="panel"):
                yield Static("⚙️ Genel Ayarlar", classes="panel-title")

                yield Label("Hedef Sure:")
                yield Input(value="9:00:00", id="duration_input")

                yield Label("Codec:")
                yield Select.from_values(["av1", "h264", "h265"], value="av1", id="codec_select")

                yield Label("Video Bitrate (Bos=Oto):")
                yield Input(placeholder="Orn: 5000k, 5M", id="bitrate_input")

                yield Label("Muzik Secimi:")
                yield Select(
                    [
                        ("🔀 Rastgele (Muzik klasorunden)", "random"),
                        ("🎵 Sabit Liste (Tum projeler ayni)", "fixed"),
                        ("🔇 Sessiz", "none"),
                    ],
                    value="random",
                    id="music_mode_select",
                )

                yield Checkbox(
                    "Her projeyi ayri ayri ozellestir", value=False, id="customize_check"
                )

        # STEP 2: Customization (Hidden initially)
        with Container(id="step2_container", classes="hidden"):
            yield Static("🔧 Proje Ozellestirme", classes="panel-title")
            yield Static("...", id="current_project_label", classes="subtitle")

            with Container(classes="panel"):
                yield Label("Muzik Modu (Bu proje icin):")
                yield Select(
                    [
                        ("Global Ayarlari Kullan", "global"),
                        ("🔀 Yeni Rastgele Liste", "random"),
                        ("🎵 Ozel Liste Sec", "specific"),
                    ],
                    value="global",
                    id="local_music_mode",
                )
                yield Static("Mevcut: Global Ayarlar", id="local_summary", classes="info-text")

        # Actions
        with Horizontal(classes="action-bar"):
            yield Button("← Geri", id="back", classes="-secondary")
            yield Button("Devam →", id="next", classes="-primary")
            yield Button("Atla (Global Kullan)", id="skip", classes="-secondary hidden")

        yield Footer()

    def on_mount(self) -> None:
        """Called when screen is mounted."""
        self._scan_files()
        self._update_pairs_table()

        # Hide step 2
        self.query_one("#step2_container").display = False
        self.query_one("#skip").display = False

    def _scan_files(self) -> None:
        """Scan for pairs and music."""
        # Scan pairs
        self.pairs = self.detector.scan()
        self.selected_indices = set(range(len(self.pairs)))

        # Scan music
        music_dir = Path.cwd() / "music"
        if music_dir.exists():
            for f in music_dir.iterdir():
                if f.is_file() and f.suffix.lower() in {".mp3", ".wav", ".flac", ".ogg", ".m4a"}:
                    if not is_background_file(f):
                        self.music_tracks.append(f)
                    else:
                        self.global_bg_files.append(f)

    def _update_pairs_table(self) -> None:
        """Update the table of detected pairs."""
        table = self.query_one("#pairs_table", DataTable)
        table.clear(columns=True)
        table.add_columns("✓", "Proje Adi", "Intro", "Loop")

        for i, pair in enumerate(self.pairs):
            icon = "✓" if i in self.selected_indices else " "
            table.add_row(icon, pair.name, pair.intro.name, pair.loop.name)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Toggle pair selection."""
        if self.step == 1:
            idx = event.cursor_row
            if idx in self.selected_indices:
                self.selected_indices.remove(idx)
            else:
                self.selected_indices.add(idx)
            self._update_pairs_table()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle buttons."""
        if event.button.id == "back":
            if self.step > 1:
                # Cancel wizard, go back to batch screen?
                # Or go back to step 1? Let's go back to batch screen for simplicity
                self.app.pop_screen()
            else:
                self.app.pop_screen()

        elif event.button.id == "next":
            if self.step == 1:
                self._finish_step_1()
            elif self.step == 2:
                self._finish_step_2_current_pair()

        elif event.button.id == "skip":
            if self.step == 2:
                # Use default settings for this pair
                self._next_pair()

    def _finish_step_1(self) -> None:
        """Validate step 1 and proceed."""
        if not self.selected_indices:
            self.notify("En az bir proje secin!", severity="error")
            return

        # Save global settings
        self.global_duration = self.query_one("#duration_input", Input).value
        self.global_bitrate = self.query_one("#bitrate_input", Input).value
        self.global_codec = self.query_one("#codec_select", Select).value
        self.music_mode = self.query_one("#music_mode_select", Select).value

        do_customize = self.query_one("#customize_check", Checkbox).value

        if self.music_mode == "fixed":
            # Show music selection screen (not implemented in this simplified wizard)
            # For now, if fixed, we might need to pick random once and use for all?
            # Or just assume "random" implies different random for each.
            # Let's say "fixed" means we need to select tracks.
            # Since we can't easily pop another screen and return with data in this architecture easily without callbacks,
            # we'll simplify: "Fixed" = Random playlist generated ONCE and used for ALL.
            pass

        if do_customize:
            self.step = 2
            self.customizing_pairs = sorted(list(self.selected_indices))
            self.current_pair_idx = 0
            self._show_step_2()
        else:
            self._generate_jobs()

    def _show_step_2(self) -> None:
        """Show customization for current pair."""
        # Switch UI
        self.query_one("#step1_container").display = False
        self.query_one("#step2_container").display = True
        self.query_one("#skip").display = True

        pair_idx = self.customizing_pairs[self.current_pair_idx]
        pair = self.pairs[pair_idx]

        self.query_one("#current_project_label", Static).update(
            f"Proje: {pair.name} ({self.current_pair_idx + 1}/{len(self.customizing_pairs)})"
        )

        # Reset inputs
        self.query_one("#local_music_mode", Select).value = "global"

    def _finish_step_2_current_pair(self) -> None:
        """Save local settings and go next."""
        pair_idx = self.customizing_pairs[self.current_pair_idx]
        mode = self.query_one("#local_music_mode", Select).value

        settings = {"music_mode": mode if mode != "global" else self.music_mode}
        self.project_settings[pair_idx] = settings

        self._next_pair()

    def _next_pair(self) -> None:
        """Move to next pair or finish."""
        self.current_pair_idx += 1
        if self.current_pair_idx >= len(self.customizing_pairs):
            self._generate_jobs()
        else:
            self._show_step_2()

    def _generate_jobs(self) -> None:
        """Generate actual jobs in the queue."""
        queue = getattr(self.app, "queue", None)
        if not queue:
            # Fallback if not initialized (shouldn't happen)
            queue = BatchQueue()

        count = 0
        for idx in self.selected_indices:
            pair = self.pairs[idx]
            settings = self.project_settings.get(idx, {})

            # Duration parse
            try:
                total_sec = parse_duration(self.global_duration)
            except:
                total_sec = 32400  # 9 hours default

            # Create Job
            job = queue.create_job()
            job.intro_path = pair.intro
            job.loop_path = pair.loop
            job.codec_family = self.global_codec
            job.duration_str = self.global_duration
            job.total_seconds = total_sec
            job.video_bitrate = self.global_bitrate if self.global_bitrate else None
            job.status = JobStatus.QUEUED

            # Music logic
            eff_music_mode = settings.get("music_mode", self.music_mode)

            if eff_music_mode == "none":
                job.tracks = []
            elif eff_music_mode == "random":
                # Pick random tracks until duration filled (approx)
                if self.music_tracks:
                    # Simple automated selection: shuffle and take enough to cover duration
                    shuffled = list(self.music_tracks)
                    random.shuffle(shuffled)
                    job.tracks = shuffled[:20]  # Limit to 20 tracks for sanity, or loop them
                else:
                    job.tracks = []

            # TODO: Handle backgrounds? For now no BGs in smart batch to keep it simple.

            job.output_path = Path.cwd() / f"{pair.name}_{self.global_codec}.mp4"

            queue.queue_job(job.id)

            count += 1

        self.notify(f"{count} is siraya eklendi!", severity="information")
        self.app.pop_screen()
