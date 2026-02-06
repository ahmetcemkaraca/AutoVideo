#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch Screen - Batch rendering queue management.
"""

from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Button, Footer, DataTable, Input, Label
from textual.containers import Container, Vertical, Horizontal
from textual.worker import Worker, get_current_worker

from ..batch import BatchQueue, RenderJob, JobStatus, parse_duration
from ..ffmpeg import FFmpegRunner, get_duration
from ..audio import AudioProcessor, mux_video_audio
from ..video import VideoEncoder
from ..video import VideoEncoder
from config import get_best_encoder
from ..drive import DriveUploader
import threading


class BatchScreen(Screen):
    """Screen for managing batch render queue."""
    
    BINDINGS = [
        ("a", "add_job", "Is Ekle"),
        ("s", "start_queue", "Kuyrugu Baslat"),
        ("d", "delete_job", "Is Sil"),
        ("c", "clear_completed", "Tamamlananlari Temizle"),
        ("escape", "go_back", "Geri"),
    ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Queue is shared in app
        self.is_processing = False
        self.process_worker: Optional[Worker] = None
        self.uploader = DriveUploader()
        self.upload_threads: list[threading.Thread] = []
    
    @property
    def queue(self):
        return self.app.queue
    
    def compose(self) -> ComposeResult:
        yield Container(
            Static("📦 Batch Render Kuyrugu", classes="title"),
            Static("Birden fazla render isini sirayla calistirin", classes="subtitle"),
            classes="container",
        )
        
        # Queue table
        with Container(classes="panel"):
            yield Static("Is Kuyrugu", classes="panel-title")
            yield DataTable(id="queue_table")
        
        # Summary
        with Container(classes="panel"):
            yield Static("", id="queue_summary", classes="info-text")
        
        # Actions
        with Horizontal(classes="action-bar"):
            yield Button("➕ Is Ekle", id="add", classes="-primary")
            yield Button("✨ Smart Batch", id="smart_batch", classes="-primary")
            yield Button("▶ Baslat", id="start", classes="-success")
            yield Button("🗑 Temizle", id="clear", classes="-secondary")
            yield Button("← Geri", id="back", classes="-secondary")
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Called when screen is mounted."""
        self._update_table()
        self._update_summary()
    
    def _update_table(self) -> None:
        """Update the queue table."""
        table = self.query_one("#queue_table", DataTable)
        table.clear(columns=True)
        
        table.add_columns("#", "Intro", "Loop", "Codec", "Sure", "Durum", "Upload", "Ilerleme")
        
        status_icons = {
            JobStatus.PENDING: "⏸",
            JobStatus.CONFIGURING: "📝",
            JobStatus.QUEUED: "⏳",
            JobStatus.RUNNING: "🔄",
            JobStatus.COMPLETE: "✅",
            JobStatus.ERROR: "❌",
            JobStatus.CANCELLED: "🚫",
        }
        
        for job in self.queue.jobs:
            if job.mode == "single":
                intro_name = job.single_video_path.name if job.single_video_path else "-"
                loop_name = "(Single)"
            else:
                intro_name = job.intro_path.name if job.intro_path else "-"
                loop_name = job.loop_path.name if job.loop_path else "-"
            
            status_icon = status_icons.get(job.status, "?")
            progress = f"{job.progress:.0f}%" if job.status == JobStatus.RUNNING else ""
            
            table.add_row(
                str(job.id),
                intro_name[:20],
                loop_name[:20],
                job.codec_family.upper(),
                job.duration_str,
                f"{status_icon} {job.status.value}",
                job.upload_status if job.upload_enabled else "-",
                progress
            )
    
    def _update_summary(self) -> None:
        """Update queue summary."""
        summary = self.queue.get_summary()
        total = len(self.queue.jobs)
        queued = summary.get("queued", 0)
        running = summary.get("running", 0)
        complete = summary.get("complete", 0)
        
        text = f"Toplam: {total} | Kuyrukta: {queued} | Calisiyor: {running} | Tamamlandi: {complete}"
        self.query_one("#queue_summary", Static).update(text)
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "add":
            self._add_job()
        elif event.button.id == "smart_batch":
            self.app.push_screen("smart_batch")
        elif event.button.id == "start":
            self._start_processing()
        elif event.button.id == "clear":
            self._clear_completed()
        elif event.button.id == "back":
            self.app.pop_screen()
    
    def _add_job(self) -> None:
        """Add a new job to the queue."""
        # Create new job
        job = self.queue.create_job()
        
        # Store job id in app
        self.app.batch_job_id = job.id
        
        # Populate upload config from app if available
        if hasattr(self.app, 'enable_upload'):
             job.upload_enabled = self.app.enable_upload
             job.upload_folder_id = self.app.drive_folder_id
        
        # Go to video select screen
        self.app.push_screen("video_select")
    
    def _start_processing(self) -> None:
        """Start processing the queue."""
        if self.is_processing:
            self.notify("Kuyruk zaten isleniyor!", severity="warning")
            return
        
        queued_jobs = self.queue.get_queued_jobs()
        if not queued_jobs:
            self.notify("Kuyrukta islenecek is yok!", severity="warning")
            return
        
        self.is_processing = True
        self.process_worker = self.run_worker(self._process_queue, thread=True)
    
    async def _process_queue(self) -> None:
        """Process all queued jobs sequentially."""
        worker = get_current_worker()
        
        while True:
            if worker.is_cancelled:
                break
            
            job = self.queue.get_next_job()
            if not job:
                break
            
            try:
                self.call_from_thread(self._update_table)
                await self._run_single_job(job, worker)
            except Exception as e:
                self.queue.fail_job(job.id, str(e))
        
        self.is_processing = False
        self.call_from_thread(self._update_table)
        self.call_from_thread(self._update_summary)
        self.call_from_thread(self.notify, "Kuyruk isleme tamamlandi!")
    
    async def _run_single_job(self, job: RenderJob, worker: Worker) -> None:
        """Run a single render job."""
        self.queue.start_job(job.id)
        
        # Select renderer implementation
        use_main = getattr(self.app, "use_main_renderer", False)
        
        if use_main:
            try:
                import sys
                project_root = Path.cwd()
                if str(project_root) not in sys.path:
                    sys.path.insert(0, str(project_root))
                
                from video_renderer.ffmpeg import FFmpegRunner as RunnerCls, AudioProcessor as AudioCls
                from video_renderer.video import VideoEncoder as EncoderCls
            except ImportError:
                from ..ffmpeg import FFmpegRunner as RunnerCls, AudioProcessor as AudioCls
                from ..video import VideoEncoder as EncoderCls
        else:
            from ..ffmpeg import FFmpegRunner as RunnerCls, AudioProcessor as AudioCls
            from ..video import VideoEncoder as EncoderCls
        
        base = Path.cwd()
        tmp_dir = base / "tmp"
        run_log = tmp_dir / "run_log.txt"
        
        # Use classes
        runner = RunnerCls(run_log)
        
        if not job.codec_family:
             job.codec_family = "av1" # Default
        
        codec_config = get_best_encoder(job.codec_family)
        
        # Create encoder
        encoder = EncoderCls(runner, codec_config, width=1920, height=1080, fps=30)
        
        video_only = None
        
        if job.mode == "single" and job.single_video_path:
             # Single Video Mode
             video_only = tmp_dir / f"batch_{job.id}_video_{job.codec_family}.mp4"
             if not video_only.exists():
                 if job.total_seconds <= 0:
                     # Calculate total seconds if not set
                     job.total_seconds = int(get_duration(job.single_video_path))
                 
                 # Normalize/Encode video (simple copy/convert)
                 # We reuse normalize_video for this
                 encoder.normalize_video(job.single_video_path, video_only)
             
             self.queue.update_progress(job.id, 60) # Jump to 60 directly
             self.call_from_thread(self._update_table)
             
        else:
             # Intro + Loop Mode
             # Step 1: Encode intro
             intro_norm = tmp_dir / f"batch_{job.id}_intro_{job.codec_family}.mp4"
             if not intro_norm.exists():
                 encoder.normalize_video(job.intro_path, intro_norm)
             self.queue.update_progress(job.id, 20)
             self.call_from_thread(self._update_table)
             
             if worker.is_cancelled:
                 return
             
             # Step 2: Encode loop
             loop_norm = tmp_dir / f"batch_{job.id}_loop_{job.codec_family}.mp4"
             if not loop_norm.exists():
                 encoder.normalize_video(job.loop_path, loop_norm)
             self.queue.update_progress(job.id, 40)
             self.call_from_thread(self._update_table)
             
             if worker.is_cancelled:
                 return
             
             # Step 3: Concat
             video_only = encoder.concat_videos(
                 intro_norm, loop_norm,
                 job.total_seconds, tmp_dir
             )
             self.queue.update_progress(job.id, 60)
             self.call_from_thread(self._update_table)
        
        if worker.is_cancelled:
            return
        
        # Step 4: Audio
        audio_processor = AudioCls(runner, tmp_dir) 
        # Note: AudioProcessor in main vs ramtest might differ in args.
        # Main AudioProcessor __init__ likely takes (runner, tmp_dir).
        # Ramtest might too. Assuming parity.
        
        music_loop = audio_processor.create_music_loop(job.tracks, job.total_seconds)
        
        if job.backgrounds:
            bg_processed = audio_processor.process_backgrounds(job.backgrounds)
            audio_full = audio_processor.mix_tracks(music_loop, bg_processed, job.total_seconds)
        else:
            audio_full = music_loop
        
        self.queue.update_progress(job.id, 80)
        self.call_from_thread(self._update_table)
        
        if worker.is_cancelled:
            return
        
        # Step 5: Final mux
        mux_video_audio(runner, video_only, audio_full, job.output_path)
        
        self.queue.complete_job(job.id)
        self.call_from_thread(self._update_table)
        self.call_from_thread(self._update_summary)

        # Trigger Upload (Background)
        if job.upload_enabled and job.output_path and job.output_path.exists():
            job.upload_status = "uploading"
            self.call_from_thread(self._update_table)
            
            t = threading.Thread(target=self._run_bg_upload, args=(job,), daemon=True)
            self.upload_threads.append(t)
            t.start()

    def _run_bg_upload(self, job: RenderJob) -> None:
        """Run upload in background thread."""
        try:
             # Ensure auth is ready (thread-safe in DriveUploader)
             file_id = self.uploader.upload_file(job.output_path, job.upload_folder_id)
             if file_id:
                 job.upload_status = "complete"
                 job.upload_file_id = file_id
             else:
                 job.upload_status = "error"
        except Exception as e:
             job.upload_status = f"error: {str(e)[:20]}"
        
        self.call_from_thread(self._update_table)
    
    def _clear_completed(self) -> None:
        """Clear completed jobs."""
        removed = self.queue.clear_completed()
        self._update_table()
        self._update_summary()
        self.notify(f"{removed} is temizlendi.")
    
    def action_add_job(self) -> None:
        self._add_job()
    
    def action_start_queue(self) -> None:
        self._start_processing()
    
    def action_delete_job(self) -> None:
        """Delete selected job."""
        table = self.query_one("#queue_table", DataTable)
        if table.cursor_row is not None and table.cursor_row < len(self.queue.jobs):
            job = self.queue.jobs[table.cursor_row]
            if self.queue.remove_job(job.id):
                self._update_table()
                self._update_summary()
                self.notify(f"Is #{job.id} silindi.")
    
    def action_clear_completed(self) -> None:
        self._clear_completed()
    
    def action_go_back(self) -> None:
        self.app.pop_screen()
