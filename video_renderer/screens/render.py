#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Render Screen - Shows render progress with live updates.

Supports both standard and RAM-optimized (ramtest) rendering modes.
"""

from pathlib import Path
from typing import Optional
import asyncio
import time
import json
import threading
import psutil
import os

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Button, Footer, ProgressBar, Log
from textual.containers import Container, Vertical, Horizontal
from textual.worker import Worker, get_current_worker

from ..ffmpeg import FFmpegRunner, FFmpegProgress, get_duration
from ..audio import AudioProcessor, mux_video_audio
from ..video import VideoEncoder
from ..config import get_render_config
from ..validator import PreRenderValidator, PostRenderValidator


class RenderStep:
    """Represents a render step."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.progress = 0.0
        self.status = "pending"  # pending, active, complete, error


class RenderScreen(Screen):
    """Screen showing render progress with unified mode support."""

    BINDINGS = [
        ("escape", "cancel", "Iptal"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.steps = [
            RenderStep("intro", "Intro Encode"),
            RenderStep("loop", "Loop Encode"),
            RenderStep("concat", "Video Concat"),
            RenderStep("audio", "Audio Isleme"),
            RenderStep("mux", "Final Mux"),
        ]
        self.current_step = 0
        self.is_running = False
        self.error_message: Optional[str] = None
        self.render_worker: Optional[Worker] = None

        # Unified mode support
        self.app_mode = getattr(self.app, "mode", "standard")
        self.mode_config = getattr(self.app, "mode_config", None)

        # Legacy ramtest_mode support (backward compatibility)
        self.ramtest_mode = self.app_mode in ["ramtest", "ramdisk"]
        self.ramtest_config = getattr(self.app, "ramtest_config", None)

        # Memory tracking
        self._memory_update_interval = 2.0  # Update every 2 seconds
        self._last_memory_update = 0

        # Rate limiting (for all modes to prevent UI flooding)
        self._update_interval = 0.1  # 100ms rate limiting
        self._last_update_time = 0

    def compose(self) -> ComposeResult:
        # Mode indicator
        mode_indicators = {
            "standard": "",
            "ramtest": " [RAM]",
            "ramdisk": " [RAMDisk]",
            "high_vram": " [VRAM]",
        }
        mode_indicator = mode_indicators.get(self.app_mode, "")

        yield Container(
            Static(f"🎬 Render Islemi{mode_indicator}", classes="title"),
            Static("", id="status_text", classes="subtitle"),
            classes="container",
        )

        # Memory info panel (for ramtest, ramdisk, high_vram modes)
        if self.app_mode in ["ramtest", "ramdisk", "high_vram"]:
            panel_class = "memory-panel" if self.app_mode == "high_vram" else "panel"
            with Container(classes=panel_class):
                yield Static("💾 Memory Usage", classes="panel-title")
                yield Static("RAM: --- | VRAM: ---", id="memory_info", classes="info-text")

        # Progress steps
        with Container(classes="panel"):
            for i, step in enumerate(self.steps, 1):
                yield Static(
                    f"○ [{i}/5] {step.description}",
                    id=f"step_{step.name}",
                    classes="progress-pending",
                )
                yield ProgressBar(total=100, show_eta=True, id=f"progress_{step.name}")

        # Log panel
        with Container(classes="panel"):
            yield Static("📋 Log", classes="panel-title")
            yield Log(id="render_log", classes="log-panel")

        with Horizontal(classes="action-bar"):
            yield Button("❌ Iptal", id="cancel", classes="-error")

        yield Footer()

    def on_mount(self) -> None:
        """Start render when mounted."""
        self.is_running = True

        # Mode-specific startup message
        mode_messages = {
            "standard": "",
            "ramtest": " (RAM-Optimized)",
            "ramdisk": " (RAM Disk)",
            "high_vram": " (High VRAM)",
        }
        mode_text = mode_messages.get(self.app_mode, "")
        self._update_status(f"Render baslatiliyor{mode_text}...")

        # Log mode configuration
        if self.mode_config and self.app_mode in ["ramtest", "ramdisk", "high_vram"]:
            from config import get_ramdisk_path

            if self.app_mode == "high_vram":
                self._log("✓ High VRAM modu aktif")
                self._log(f"  - GPU buffer artirildi")
            else:
                if self.mode_config.use_ramdisk:
                    ramdisk = get_ramdisk_path()
                    if ramdisk:
                        self._log(f"✓ RAM Disk aktif: {ramdisk}")
                    else:
                        self._log("ℹ️  RAM Disk mevcut degil (disk kullaniliyor)")

                if self.mode_config.high_vram:
                    self._log("✓ High VRAM modu aktif")

                if self.mode_config.chunk_long_videos:
                    self._log("✓ Video parcalama aktif (2 saatlik chunk'lar)")

        # Start render in worker thread
        self.render_worker = self.run_worker(self._run_render, thread=True)

    def _update_status(self, text: str) -> None:
        """Update status text."""
        try:
            self.query_one("#status_text", Static).update(text)
        except:
            pass

    def _update_memory_info(self):
        """Update memory usage information (for ramtest, ramdisk, high_vram modes)."""
        if self.app_mode not in ["ramtest", "ramdisk", "high_vram"]:
            return

        current_time = time.time()
        if current_time - self._last_memory_update < self._memory_update_interval:
            return

        self._last_memory_update = current_time

        try:
            process = psutil.Process(os.getpid())
            ram_info = process.memory_info()

            # RAM usage
            ram_mb = ram_info.rss / (1024 * 1024)
            ram_percent = process.memory_percent()

            # Try to get GPU memory (nvidia-smi)
            vram_mb = 0
            vram_percent = 0
            try:
                import subprocess

                # Get used memory
                result_used = subprocess.run(
                    ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                    capture_output=True,
                    text=True,
                    timeout=1,
                )
                # Get total memory
                result_total = subprocess.run(
                    ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                    capture_output=True,
                    text=True,
                    timeout=1,
                )
                if result_used.returncode == 0 and result_total.returncode == 0:
                    vram_mb = int(result_used.stdout.strip().split("\n")[0])
                    vram_total_mb = int(result_total.stdout.strip().split("\n")[0])
                    vram_percent = (vram_mb / vram_total_mb) * 100
            except Exception:
                pass

            # Format memory text based on mode
            if self.app_mode == "high_vram":
                memory_text = f"RAM: {ram_mb:.0f}MB ({ram_percent:.1f}%) | VRAM: {vram_mb}MB ({vram_percent:.1f}%)"
            else:
                memory_text = f"RAM: {ram_mb:.0f}MB ({ram_percent:.1f}%) | VRAM: {vram_mb}MB"

            try:
                self.query_one("#memory_info", Static).update(memory_text)
            except Exception:
                pass
        except Exception as e:
            pass  # Silently fail memory tracking

    def _update_step_status(self, step_name: str, status: str, progress: float = 0) -> None:
        """Update step status with rate limiting to prevent UI flooding."""
        import time

        # Update memory info periodically
        self._update_memory_info()

        # Rate limiting: check if enough time has passed since last update
        current_time = time.time()
        if status == "active" and hasattr(self, "_last_update_time"):
            if current_time - self._last_update_time < self._update_interval:
                return

        self._last_update_time = current_time

        try:
            step_widget = self.query_one(f"#step_{step_name}", Static)
            idx = next(i for i, s in enumerate(self.steps) if s.name == step_name) + 1

            if status == "active":
                step_widget.update(f"● [{idx}/5] {self.steps[idx-1].description}")
                step_widget.set_classes("progress-active")
            elif status == "complete":
                step_widget.update(f"✓ [{idx}/5] {self.steps[idx-1].description}")
                step_widget.set_classes("progress-complete")
            elif status == "error":
                step_widget.update(f"✗ [{idx}/5] {self.steps[idx-1].description}")
                step_widget.set_classes("error-text")

            progress_bar = self.query_one(f"#progress_{step_name}", ProgressBar)
            progress_bar.progress = progress
        except:
            pass

    def _log(self, message: str) -> None:
        """Add message to log."""
        try:
            log = self.query_one("#render_log", Log)
            log.write_line(message)
        except:
            pass

    async def _run_render(self) -> None:
        """Run the render pipeline."""
        worker = get_current_worker()
        app = self.app

        base = Path.cwd()
        tmp_dir = base / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        run_log = tmp_dir / "run_log.txt"

        try:
            # Get data from app
            intro_path = getattr(app, "intro_path", None)
            loop_path = getattr(app, "loop_path", None)
            single_video_path = getattr(app, "single_video_path", None)
            chosen_tracks = getattr(app, "chosen_tracks", [])
            chosen_bgs = getattr(app, "chosen_bgs", [])
            codec_family = getattr(app, "codec_family", "av1")
            codec_config = getattr(app, "codec_config", None)
            total_seconds = getattr(app, "total_seconds", 32400)
            out_path = getattr(app, "out_path", base / "output.mp4")

            # Check for resume from session
            session = getattr(app, "session", None)
            if session:
                if session.get("mode") == "single":
                    single_video_path = Path(session["video"])
                else:
                    intro_path = Path(session["intro"])
                    loop_path = Path(session["loop"])
                chosen_tracks = [Path(p) for p in session["tracks"]]
                chosen_bgs = [(Path(b["path"]), b["db"]) for b in session.get("bgs", [])]
                codec_family = session["codec"]
                codec_config = codec_config or app.codec_config
                total_seconds = session["duration_sec"]
                out_path = Path(session["out"])

            if not codec_config:
                from config import get_best_encoder

                codec_config = get_best_encoder(codec_family)

            # ═══════════════════════════════════════════════════════════════════
            # PRE-RENDER VALIDATION
            # ═══════════════════════════════════════════════════════════════════

            # Check if validation should be skipped
            skip_validation = getattr(app, "skip_validation", False)
            if not skip_validation:
                self.call_from_thread(self._log, "Doğrulama yapılıyor...")

                pre_validator = PreRenderValidator(
                    target_width=getattr(codec_config, "width", 1920),
                    target_height=getattr(codec_config, "height", 1080),
                    target_fps=getattr(codec_config, "fps", 60)
                )

                pre_result = pre_validator.validate_render_specs(
                    intro_path=intro_path,
                    loop_path=loop_path,
                    single_path=single_video_path,
                    tracks=chosen_tracks,
                    target_duration=total_seconds,
                    output_dir=out_path.parent
                )

                # Log validation results
                if pre_result.errors:
                    self.call_from_thread(self._log, f"✗ Doğrulama hatası: {len(pre_result.errors)} hata")
                    for error in pre_result.errors:
                        self.call_from_thread(self._log, f"  - {error.message}")
                elif pre_result.warnings:
                    self.call_from_thread(self._log, f"⚠ Doğrulama uyarısı: {len(pre_result.warnings)} uyarı")

                # Show validation screen if issues found
                if not pre_result.valid:
                    from ..screens.validation import show_validation_result

                    # Show red notification for validation failure
                    self.call_from_thread(
                        app.notify,
                        f"❌ Doğrulama başarısız: {len(pre_result.errors)} hata tespit edildi",
                        title="Doğrulama Hatası",
                        severity="error",
                        timeout=5
                    )

                    self.call_from_thread(show_validation_result, app, pre_result)

                    # Wait for user decision
                    if worker.is_cancelled:
                        return

                    # Check if user chose to continue anyway
                    if not getattr(app, "skip_validation", False):
                        # User chose to retry or go back
                        return
                elif pre_result.warnings:
                    # Show warnings but allow continue
                    self.call_from_thread(
                        app.notify,
                        f"⚠️ Doğrulama uyarısı: {len(pre_result.warnings)} uyarı tespit edildi",
                        title="Doğrulama Uyarısı",
                        severity="warning",
                        timeout=3
                    )
                    self.call_from_thread(self._log, "⚠️ Uyarılarla devam ediliyor...")

            runner = FFmpegRunner(run_log)

            # Define output paths
            intro_norm = tmp_dir / f"intro_norm_{codec_family}.mp4"
            loop_norm = tmp_dir / f"loop_norm_{codec_family}.mp4"
            video_only_single = tmp_dir / f"video_only_single_{codec_family}.mp4"

            # Create encoder
            encoder = VideoEncoder(runner, codec_config, width=1920, height=1080, fps=30)

            # ═══════════════════════════════════════════════════════════════════
            # STEP 1-3: Video Processing (Intro/Loop or Single)
            # ═══════════════════════════════════════════════════════════════════

            if worker.is_cancelled:
                return

            if single_video_path:
                self.call_from_thread(self._update_step_status, "intro", "active")
                self.call_from_thread(self._log, f"Tek video encode: {single_video_path.name}")

                if not total_seconds or total_seconds <= 0:
                    total_seconds = int(get_duration(single_video_path))

                if video_only_single.exists():
                    video_only = video_only_single
                    self.call_from_thread(self._log, "Video zaten var, atlaniyor...")
                else:

                    def single_progress(p: FFmpegProgress):
                        self.call_from_thread(
                            self._update_step_status, "intro", "active", p.percent
                        )

                    video_only = encoder.normalize_video(
                        single_video_path, video_only_single, single_progress
                    )

                self.call_from_thread(self._update_step_status, "intro", "complete", 100)
                self.call_from_thread(self._update_step_status, "loop", "complete", 100)
                self.call_from_thread(self._update_step_status, "concat", "complete", 100)
            else:
                # Intro encode
                self.call_from_thread(self._update_step_status, "intro", "active")
                self.call_from_thread(self._log, f"Intro encode: {intro_path.name}")

                if intro_norm.exists():
                    self.call_from_thread(self._log, "Intro zaten var, atlaniyor...")
                else:

                    def intro_progress(p: FFmpegProgress):
                        self.call_from_thread(
                            self._update_step_status, "intro", "active", p.percent
                        )

                    encoder.normalize_video(intro_path, intro_norm, intro_progress)

                self.call_from_thread(self._update_step_status, "intro", "complete", 100)

                # Loop encode
                if worker.is_cancelled:
                    return

                self.call_from_thread(self._update_step_status, "loop", "active")
                self.call_from_thread(self._log, f"Loop encode: {loop_path.name}")

                if loop_norm.exists():
                    self.call_from_thread(self._log, "Loop zaten var, atlaniyor...")
                else:

                    def loop_progress(p: FFmpegProgress):
                        self.call_from_thread(self._update_step_status, "loop", "active", p.percent)

                    encoder.normalize_video(loop_path, loop_norm, loop_progress)

                self.call_from_thread(self._update_step_status, "loop", "complete", 100)

                # Concat
                if worker.is_cancelled:
                    return

                self.call_from_thread(self._update_step_status, "concat", "active")
                self.call_from_thread(self._log, "Video birlestiriliyor...")

                video_only_files = list(tmp_dir.glob("video_only_*.mp4"))
                if video_only_files:
                    video_only = video_only_files[0]
                    self.call_from_thread(self._log, "Concat zaten var, atlaniyor...")
                else:

                    def concat_progress(p: FFmpegProgress):
                        self.call_from_thread(
                            self._update_step_status, "concat", "active", p.percent
                        )

                    video_only = encoder.concat_videos(
                        intro_norm, loop_norm, total_seconds, tmp_dir, concat_progress
                    )

                self.call_from_thread(self._update_step_status, "concat", "complete", 100)

            # ═══════════════════════════════════════════════════════════════════
            # STEP 4: Audio
            # ═══════════════════════════════════════════════════════════════════

            if worker.is_cancelled:
                return

            self.call_from_thread(self._update_step_status, "audio", "active")
            self.call_from_thread(self._log, "Audio isleniyor...")

            audio_processor = AudioProcessor(runner, tmp_dir)

            music_loop_path = tmp_dir / "music_loop.w64"
            audio_mixed_path = tmp_dir / "audio_mixed.w64"

            if chosen_bgs and audio_mixed_path.exists():
                audio_full = audio_mixed_path
                self.call_from_thread(self._log, "Audio zaten var, atlaniyor...")
            elif not chosen_bgs and music_loop_path.exists():
                audio_full = music_loop_path
                self.call_from_thread(self._log, "Audio zaten var, atlaniyor...")
            else:
                # Validate and process tracks
                self.call_from_thread(self._log, "Track'ler dogrulaniyor...")

                valid_tracks, invalid = audio_processor.validate_tracks(chosen_tracks)
                if invalid:
                    self.call_from_thread(self._log, f"Uyari: {len(invalid)} bozuk track atlandi")

                if not valid_tracks:
                    raise ValueError("Hic gecerli track yok!")

                self.call_from_thread(
                    self._log, f"{len(valid_tracks)} track ile loop olusturuluyor..."
                )

                music_loop = audio_processor.create_music_loop(
                    valid_tracks, total_seconds, pre_validated=True
                )

                if chosen_bgs:
                    self.call_from_thread(self._log, "Background sesler ekleniyor...")
                    bg_processed = audio_processor.process_backgrounds(chosen_bgs)
                    audio_full = audio_processor.mix_tracks(music_loop, bg_processed, total_seconds)
                else:
                    audio_full = music_loop

            self.call_from_thread(self._update_step_status, "audio", "complete", 100)

            # ═══════════════════════════════════════════════════════════════════
            # STEP 5: Final Mux
            # ═══════════════════════════════════════════════════════════════════

            if worker.is_cancelled:
                return

            self.call_from_thread(self._update_step_status, "mux", "active")
            self.call_from_thread(self._log, f"Final mux: {out_path.name}")

            if out_path.exists():
                self.call_from_thread(self._log, "Cikti zaten var, atlaniyor...")
            else:

                def mux_progress(p: FFmpegProgress):
                    self.call_from_thread(self._update_step_status, "mux", "active", p.percent)

                mux_video_audio(runner, video_only, audio_full, out_path, mux_progress)

            self.call_from_thread(self._update_step_status, "mux", "complete", 100)

            # ═══════════════════════════════════════════════════════════════════
            # POST-RENDER VALIDATION
            # ═══════════════════════════════════════════════════════════════════

            self.call_from_thread(self._log, "Çıktı doğrulanıyor...")

            post_validator = PostRenderValidator()

            target_specs = {
                "codec": codec_family if codec_family else "h264",
                "width": getattr(codec_config, "width", 1920) if codec_config else 1920,
                "height": getattr(codec_config, "height", 1080) if codec_config else 1080,
                "fps": getattr(codec_config, "fps", 60) if codec_config else 60,
            }

            post_result = post_validator.validate_output(
                output_path=out_path,
                target_duration=total_seconds,
                target_specs=target_specs
            )

            if not post_result.valid:
                self.call_from_thread(self._log, f"✗ Çıktı doğrulaması başarısız")
                # Show red notification for post-render validation failure
                self.call_from_thread(
                    app.notify,
                    f"❌ Çıktı doğrulaması başarısız: {len(post_result.errors)} hata tespit edildi",
                    title="Çıktı Doğrulama Hatası",
                    severity="error",
                    timeout=5
                )
                from ..screens.validation import show_validation_result
                self.call_from_thread(show_validation_result, app, post_result)
            elif post_result.warnings:
                self.call_from_thread(self._log, f"⚠️ Çıktı doğrulaması: {len(post_result.warnings)} uyarı")
                # Show warning notification
                self.call_from_thread(
                    app.notify,
                    f"⚠️ Çıktı doğrulaması uyarısı: {len(post_result.warnings)} uyarı tespit edildi",
                    title="Çıktı Doğrulama Uyarısı",
                    severity="warning",
                    timeout=3
                )
            else:
                self.call_from_thread(self._log, "✓ Çıktı doğrulaması başarılı")

            # ═══════════════════════════════════════════════════════════════════
            # COMPLETE
            # ═══════════════════════════════════════════════════════════════════

            self.call_from_thread(self._log, "✓ Render tamamlandi!")
            self.call_from_thread(self._update_status, "Tamamlandi!")

            # Store result with validation info
            app.render_result = {
                "success": True,
                "output": out_path,
                "duration": get_duration(out_path) if out_path.exists() else 0,
                "validation": {
                    "pre_render": skip_validation,
                    "post_render": post_result.valid,
                    "issues": len(post_result.issues),
                    "post_result": post_result,  # Store full validation result for export
                }
            }

            # Go to complete screen
            self.call_from_thread(self._go_to_complete)

        except Exception as e:
            import traceback

            self.error_message = str(e)
            self.call_from_thread(self._log, f"✗ Hata: {e}")
            self.call_from_thread(self._update_status, f"Hata: {e}")

            # Mark current step as error
            step_name = (
                self.steps[self.current_step].name if self.current_step < len(self.steps) else "mux"
            )
            self.call_from_thread(self._update_step_status, step_name, "error")

            # Show error buttons
            self.call_from_thread(self._show_error_options)

    def _go_to_complete(self) -> None:
        """Navigate to complete screen."""
        self.app.push_screen("complete")

    def _show_error_options(self) -> None:
        """Show error recovery options."""
        try:
            action_bar = self.query_one(".action-bar", Horizontal)
            action_bar.remove_children()
            action_bar.mount(Button("🔄 Tekrar Dene", id="retry", classes="-primary"))
            action_bar.mount(Button("🆕 Yeni Render", id="new", classes="-secondary"))
            action_bar.mount(Button("🚪 Cikis", id="quit", classes="-error"))
        except:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel":
            self._cancel_render()
        elif event.button.id == "retry":
            self.app.pop_screen()
            self.app.push_screen("render")
        elif event.button.id == "new":
            self.app.pop_screen()
            self.app.push_screen("video_select")
        elif event.button.id == "quit":
            self.app.exit()

    def _cancel_render(self) -> None:
        """Cancel the render."""
        if self.render_worker:
            self.render_worker.cancel()
        self.app.pop_screen()

    def action_cancel(self) -> None:
        """Cancel action."""
        self._cancel_render()
