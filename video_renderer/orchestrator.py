#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
End-to-End Orchestration Layer for AutoVideo.

Ties all automation components into a single CLI command for full pipeline execution.

Components:
- Drive sync: Pulls new assets from Google Drive
- Hash ledger: Prevents duplicate renders
- Content rules: Theme detection, music selection
- Render pipeline: Existing batch/video rendering
- YouTube upload: Scheduled publishing (5-day delay)
- State tracking: Persistent resume capability
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

import threading

logger = logging.getLogger(__name__)


DRIVE_FOLDER_ID = "1KIzD1pnY6Kat-HIIAsCcGH_uqNXQnzp6"
SCHEDULED_PUBLISH_DAYS = 5
LEDGER_PATH = Path("config/ledger.json")
STATE_PATH = Path("state.json")


@dataclass
class OrchestratorJob:
    intro_path: Path
    loop_path: Path
    theme: Optional[str]
    music_path: Optional[Path]
    bg_paths: List[Path]
    music_volume_db: Optional[float]
    duration_seconds: int
    output_path: Optional[Path] = None
    rendered: bool = False
    video_id: Optional[str] = None
    scheduled_publish_at: Optional[str] = None
    error: Optional[str] = None


@dataclass
class OrchestratorRun:
    started_at: str
    completed_at: Optional[str] = None
    synced_assets: List[str] = field(default_factory=list)
    skipped_duplicates: List[str] = field(default_factory=list)
    jobs: List[dict] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "OrchestratorRun":
        return cls(**data)


class OrchestratorState:
    THREAD_LOCK = threading.RLock()

    def __init__(self, state_file: Path = STATE_PATH):
        self.state_file = state_file
        self._run: Optional[OrchestratorRun] = None
        self._load()

    def _load(self) -> None:
        if not self.state_file.exists():
            self._run = OrchestratorRun(started_at=datetime.now(timezone.utc).isoformat())
            return
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            self._run = OrchestratorRun.from_dict(data)
        except Exception:
            self._run = OrchestratorRun(started_at=datetime.now(timezone.utc).isoformat())

    def _save(self) -> None:
        if self._run is None:
            return
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._run.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.state_file)

    def start_run(self) -> OrchestratorRun:
        with self.THREAD_LOCK:
            self._run = OrchestratorRun(started_at=datetime.now(timezone.utc).isoformat())
            self._save()
            return self._run

    def add_synced(self, filenames: List[str]) -> None:
        with self.THREAD_LOCK:
            if self._run:
                self._run.synced_assets.extend(filenames)
                self._save()

    def add_skipped(self, names: List[str]) -> None:
        with self.THREAD_LOCK:
            if self._run:
                self._run.skipped_duplicates.extend(names)
                self._save()

    def add_job(self, job: OrchestratorJob) -> None:
        with self.THREAD_LOCK:
            if self._run:
                self._run.jobs.append(asdict(job))
                self._save()

    def add_error(self, msg: str) -> None:
        with self.THREAD_LOCK:
            if self._run:
                self._run.errors.append(msg)
                self._save()

    def complete_run(self) -> None:
        with self.THREAD_LOCK:
            if self._run:
                self._run.completed_at = datetime.now(timezone.utc).isoformat()
                self._save()

    @property
    def current_run(self) -> Optional[OrchestratorRun]:
        return self._run

    def get_status(self) -> dict:
        if self._run is None:
            return {"status": "no_run", "jobs": [], "errors": [], "synced": [], "skipped": []}
        return {
            "status": "completed" if self._run.completed_at else "running",
            "started_at": self._run.started_at,
            "completed_at": self._run.completed_at,
            "synced_assets": self._run.synced_assets,
            "skipped_duplicates": self._run.skipped_duplicates,
            "jobs": self._run.jobs,
            "errors": self._run.errors,
            "total_jobs": len(self._run.jobs),
            "rendered": sum(1 for j in self._run.jobs if j.get("rendered")),
            "uploaded": sum(1 for j in self._run.jobs if j.get("video_id")),
            "failed": sum(1 for j in self._run.jobs if j.get("error")),
        }


class Orchestrator:
    def __init__(
        self,
        drive_folder_id: str = DRIVE_FOLDER_ID,
        base_dir: Optional[Path] = None,
        scheduled_days: int = SCHEDULED_PUBLISH_DAYS,
        dry_run: bool = False,
    ):
        self.base_dir = base_dir or Path.cwd()
        self.drive_folder_id = drive_folder_id
        self.scheduled_days = scheduled_days
        self.dry_run = dry_run
        self.state = OrchestratorState(self.base_dir / STATE_PATH)

    def _print(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] {msg}")

    def _log(self, level: str, msg: str) -> None:
        getattr(logger, level.lower(), logger.info)(msg)

    def sync(self) -> bool:
        self._print("=== DRIVE SYNC ===")
        self._log("info", "Starting Google Drive sync")

        try:
            from video_renderer.drive_sync import DriveSyncService

            service = DriveSyncService(
                root_folder_id=self.drive_folder_id,
                base_dir=self.base_dir,
            )
            result = service.sync()

            synced = [str(p.name) for p in result.downloaded]
            self.state.add_synced(synced)

            self._print(f"  Downloaded: {len(result.downloaded)}")
            for f in result.downloaded:
                self._print(f"    + {f.name}")

            if result.skipped:
                self._print(f"  Skipped (already synced): {len(result.skipped)}")

            if result.errors:
                self._print(f"  Errors: {len(result.errors)}")
                for err in result.errors:
                    self._print(f"    ! {err}")
                    self.state.add_error(err)

            return True

        except ImportError as e:
            self._print(f"  ERROR: Cannot import drive_sync: {e}")
            self._log("error", f"Drive sync import error: {e}")
            return False
        except Exception as e:
            self._print(f"  ERROR: {e}")
            self._log("error", f"Drive sync failed: {e}")
            self.state.add_error(str(e))
            return False

    def _get_render_jobs(self) -> List[OrchestratorJob]:
        self._print("=== SCANNING RENDER CANDIDATES ===")

        try:
            from video_renderer.batch import SmartBatchDetector

            detector = SmartBatchDetector(self.base_dir)
            pairs = detector.scan()

            if not pairs:
                self._print("  No intro/loop pairs found.")
                return []

            self._print(f"  Found {len(pairs)} intro/loop pair(s)")

            try:
                from video_renderer.hash_ledger import HashLedger

                ledger = HashLedger(ledger_file=self.base_dir / LEDGER_PATH)
            except ImportError:
                ledger = None

            try:
                from video_renderer.content_rules import ContentRulesEngine

                music_root = self.base_dir / "music"
                rules_engine = ContentRulesEngine(
                    music_root=music_root if music_root.exists() else None,
                    allow_visual_fallback=False,
                )
            except ImportError:
                rules_engine = None

            jobs: List[OrchestratorJob] = []
            for pair in pairs:
                self._print(f"  Checking: {pair.name}")

                if ledger and ledger.is_registered(intro_path=pair.intro, loop_path=pair.loop):
                    self._print(f"    SKIP (already rendered)")
                    self.state.add_skipped([pair.name])
                    continue

                theme = None
                music_path = None
                bg_paths: List[Path] = []
                music_volume_db = None
                duration_seconds = 8 * 3600

                if rules_engine:
                    try:
                        result = rules_engine.analyze(pair.intro, pair.loop)
                        theme = result.theme
                        music_path = result.music_path
                        bg_paths = list(result.background_paths)
                        music_volume_db = result.music_volume_db
                        duration_seconds = result.duration_seconds or (8 * 3600)
                        self._print(f"    Theme: {theme or 'auto'}, Music: {music_path.name if music_path else 'none'}")
                    except Exception as e:
                        self._print(f"    Rules engine warning: {e}")

                job = OrchestratorJob(
                    intro_path=pair.intro,
                    loop_path=pair.loop,
                    theme=theme,
                    music_path=music_path,
                    bg_paths=bg_paths,
                    music_volume_db=music_volume_db,
                    duration_seconds=duration_seconds,
                )
                jobs.append(job)
                self._print(f"    QUEUED for render")

            self._print(f"  Jobs to process: {len(jobs)}")
            return jobs

        except ImportError as e:
            self._print(f"  ERROR: Cannot import batch/renderer: {e}")
            self._log("error", f"Renderer import error: {e}")
            return []
        except Exception as e:
            self._print(f"  ERROR: {e}")
            self._log("error", f"Job scan failed: {e}")
            self.state.add_error(str(e))
            return []

    def _render_job(self, job: OrchestratorJob) -> OrchestratorJob:
        self._print(f"  Rendering: {job.intro_path.name} + {job.loop_path.name}")
        self._log("info", f"Rendering job: {job.intro_path.name}")

        if self.dry_run:
            self._print("    DRY RUN - skipping actual render")
            job.rendered = True
            job.output_path = self.base_dir / f"final_{job.intro_path.stem}_dry.mp4"
            return job

        try:
            from concurrent.futures import ThreadPoolExecutor
            from video_renderer.ffmpeg import FFmpegRunner
            from video_renderer.video import VideoEncoder
            from video_renderer.audio import AudioProcessor, mux_video_audio, is_background_file
            from video_renderer.config import get_best_encoder

            codec_family = "libx264"
            codec_config = get_best_encoder(codec_family)
            tmp_dir = self.base_dir / "tmp"
            tmp_dir.mkdir(parents=True, exist_ok=True)

            out_name = f"final_{job.intro_path.stem}_{codec_family}.mp4"
            job.output_path = self.base_dir / out_name

            runner_video = FFmpegRunner(tmp_dir / "run_log_video.txt")
            runner_audio = FFmpegRunner(tmp_dir / "run_log_audio.txt")

            encoder = VideoEncoder(
                runner=runner_video,
                codec_config=codec_config,
                width=1920,
                height=1080,
                fps=60.0,
            )

            audio_processor = AudioProcessor(runner_audio, tmp_dir)

            intro_norm = tmp_dir / f"intro_norm_{codec_family}.mp4"
            loop_norm = tmp_dir / f"loop_norm_{codec_family}.mp4"

            def encode_video():
                encoder.normalize_video(job.intro_path, intro_norm, None, keep_audio=False)
                encoder.normalize_video(job.loop_path, loop_norm, None, keep_audio=False)
                return encoder.concat_videos(intro_norm, loop_norm, job.duration_seconds, tmp_dir, None, keep_audio=False)

            def process_audio():
                audio_tracks = [job.music_path] if job.music_path else []
                if audio_tracks:
                    music_loop = audio_processor.create_music_loop(audio_tracks, job.duration_seconds)
                    if job.bg_paths:
                        processed_bgs = audio_processor.process_backgrounds(
                            [(bg, job.music_volume_db or -13.0) for bg in job.bg_paths]
                        )
                        return audio_processor.mix_tracks(music_loop, processed_bgs, job.duration_seconds)
                    return music_loop
                return None

            with ThreadPoolExecutor(max_workers=2) as executor:
                video_only = executor.submit(encode_video).result()
                audio_full = executor.submit(process_audio).result()

            if audio_full is None:
                import subprocess
                silence_path = tmp_dir / "silence.w64"
                subprocess.run(
                    ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                     "-t", str(job.duration_seconds), "-c:a", "pcm_s16le", "-f", "w64", str(silence_path)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                audio_full = silence_path

            time.sleep(0.5)

            mux_runner = FFmpegRunner(tmp_dir / "run_log_mux.txt")
            mux_video_audio(
                mux_runner, video_only, audio_full, job.output_path,
                keep_video_audio=False,
            )

            job.rendered = True
            self._print(f"    DONE: {job.output_path.name}")

            try:
                from video_renderer.hash_ledger import HashLedger
                ledger = HashLedger(ledger_file=self.base_dir / LEDGER_PATH)
                ledger.register(intro_path=job.intro_path, loop_path=job.loop_path, output_path=job.output_path)
                self._print(f"    Ledger updated")
            except Exception as e:
                self._print(f"    Ledger warning: {e}")

            for f in tmp_dir.glob("*.mp4"):
                if f != job.output_path:
                    f.unlink(missing_ok=True)
            for f in tmp_dir.glob("*.w64"):
                f.unlink(missing_ok=True)

        except Exception as e:
            self._print(f"    RENDER ERROR: {e}")
            self._log("error", f"Render failed for {job.intro_path.name}: {e}")
            job.error = str(e)

        return job

    def _upload_job(self, job: OrchestratorJob) -> OrchestratorJob:
        if not job.rendered or not job.output_path or not job.output_path.exists():
            if not job.error:
                job.error = "Cannot upload: render incomplete or output missing"
            return job

        if self.dry_run:
            self._print(f"  DRY RUN - would upload: {job.output_path.name}")
            job.video_id = "DRY_RUN_VIDEO_ID"
            job.scheduled_publish_at = self._scheduled_publish_at()
            return job

        self._print(f"  Uploading: {job.output_path.name}")
        self._log("info", f"Uploading: {job.output_path.name}")

        try:
            scheduled = self._scheduled_publish_at()
            job.scheduled_publish_at = scheduled

            upload_path = str(Path(__file__).parent.parent / "VideoAutomation" / "automation")
            if upload_path not in sys.path:
                sys.path.insert(0, upload_path)

            from automation.youtube_v2 import YouTubeUploader as YouTubeUploaderV2

            uploader = YouTubeUploaderV2()
            uploader.authenticate()

            video_id = self._upload_scheduled(
                uploader,
                job.output_path,
                title=self._make_title(job),
                description=self._make_description(job),
                tags=self._make_tags(job),
                scheduled_publish_at=scheduled,
            )

            if video_id:
                job.video_id = video_id
                self._print(f"    Uploaded! Video ID: {video_id}")
                self._print(f"    Scheduled: {scheduled}")
            else:
                job.error = "Upload failed"

        except FileNotFoundError as e:
            self._print(f"  UPLOAD ERROR: YouTube credentials not found: {e}")
            self._log("error", f"YouTube credentials missing: {e}")
            job.error = f"YouTube credentials not configured: {e}"
        except Exception as e:
            self._print(f"  UPLOAD ERROR: {e}")
            self._log("error", f"Upload failed for {job.output_path.name}: {e}")
            job.error = str(e)

        return job

    def _scheduled_publish_at(self) -> str:
        scheduled = datetime.now(timezone.utc) + timedelta(days=self.scheduled_days)
        return scheduled.replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def _upload_scheduled(
        self,
        uploader,
        video_path: Path,
        title: str,
        description: str,
        tags: List[str],
        scheduled_publish_at: str,
    ) -> Optional[str]:
        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": tags[:500],
                "categoryId": "10",
            },
            "status": {
                "privacyStatus": "private",
                "publishAt": scheduled_publish_at,
                "selfDeclaredMadeForKids": False,
            }
        }

        from googleapiclient.http import MediaFileUpload

        media = MediaFileUpload(str(video_path), mimetype="video/*", resumable=True, chunksize=5 * 1024 * 1024)

        request = uploader.youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        response = None
        while response is None:
            _, response = request.next_chunk()

        return response.get("id") if response else None

    def _make_title(self, job: OrchestratorJob) -> str:
        hours = job.duration_seconds // 3600
        theme = job.theme or "Music"
        return f"{hours} Hour {theme.title()} Music | Relaxing Background | LoFi Jazz Medieval"

    def _make_description(self, job: OrchestratorJob) -> str:
        hours = job.duration_seconds // 3600
        return (
            f"{hours} hours of relaxing {job.theme or 'music'} background sounds.\n\n"
            f"Created with AutoVideo pipeline.\n\n"
            f"#music #background #relaxation #lofi #jazz #medieval"
        )

    def _make_tags(self, job: OrchestratorJob) -> List[str]:
        tags = ["music", "background", "relaxation", "lofi", "jazz", "medieval", "ambient"]
        if job.theme:
            tags.append(job.theme)
        return tags

    def run_sync_only(self) -> bool:
        self.state.start_run()
        success = self.sync()
        if success:
            self._print("=== SYNC COMPLETE ===")
        else:
            self._print("=== SYNC FAILED ===")
        return success

    def run_render_only(self) -> bool:
        self.state.start_run()
        self._print("=== RENDER MODE (no upload) ===")
        jobs = self._get_render_jobs()
        for job in jobs:
            self.state.add_job(job)
            job = self._render_job(job)
            if job.rendered:
                self._print(f"  Rendered: {job.output_path.name}")
            elif job.error:
                self._print(f"  Error: {job.error}")
        self.state.complete_run()
        return True

    def run_full(self) -> bool:
        self.state.start_run()
        self._print("=== FULL AUTOMATION ===")

        if not self.sync():
            self._print("SYNC FAILED - aborting pipeline")
            self.state.complete_run()
            return False

        jobs = self._get_render_jobs()
        if not jobs:
            self._print("No new render jobs found.")
            self.state.complete_run()
            return True

        for i, job in enumerate(jobs, 1):
            self._print(f"\n--- Job {i}/{len(jobs)} ---")
            self.state.add_job(job)
            job = self._render_job(job)
            if job.error:
                self.state.add_error(f"Job {i} render error: {job.error}")
                continue
            job = self._upload_job(job)
            if job.error:
                self.state.add_error(f"Job {i} upload error: {job.error}")

        self.state.complete_run()

        rendered = sum(1 for j in self.state.current_run.jobs if j.get("rendered"))
        uploaded = sum(1 for j in self.state.current_run.jobs if j.get("video_id"))
        errors = len(self.state.current_run.errors)

        self._print(f"\n=== SUMMARY ===")
        self._print(f"  Rendered: {rendered}")
        self._print(f"  Uploaded: {uploaded}")
        self._print(f"  Errors:   {errors}")

        return errors == 0

    def status(self) -> None:
        st = self.state.get_status()
        self._print("=== ORCHESTRATOR STATUS ===")
        self._print(f"  Status:   {st['status']}")
        self._print(f"  Started:  {st.get('started_at', 'N/A')}")
        if st.get("completed_at"):
            self._print(f"  Completed: {st['completed_at']}")
        self._print(f"  Synced:   {len(st.get('synced_assets', []))}")
        self._print(f"  Skipped:  {len(st.get('skipped_duplicates', []))}")
        self._print(f"  Jobs:     {st.get('total_jobs', 0)} ({st.get('rendered', 0)} rendered, {st.get('uploaded', 0)} uploaded, {st.get('failed', 0)} failed)")
        if st.get("errors"):
            self._print(f"  Errors:")
            for err in st["errors"]:
                self._print(f"    - {err}")


def run(args: Optional[List[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="video_renderer",
        description="AutoVideo End-to-End Orchestration Layer",
    )
    parser.add_argument(
        "--auto", action="store_true",
        help="Full automation: sync + render + upload to YouTube"
    )
    parser.add_argument(
        "--sync", action="store_true",
        help="Sync assets from Google Drive only"
    )
    parser.add_argument(
        "--render-only", action="store_true",
        help="Render videos without uploading to YouTube"
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Show current pipeline status"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Simulate without making changes"
    )
    parser.add_argument(
        "--folder-id", type=str, default=DRIVE_FOLDER_ID,
        help=f"Google Drive root folder ID (default: {DRIVE_FOLDER_ID})"
    )
    parser.add_argument(
        "--scheduled-days", type=int, default=SCHEDULED_PUBLISH_DAYS,
        help=f"Days until YouTube publish (default: {SCHEDULED_PUBLISH_DAYS})"
    )

    parsed = parser.parse_args(args)

    if not any([parsed.auto, parsed.sync, parsed.render_only, parsed.status]):
        parser.print_help()
        return 0

    orchestrator = Orchestrator(
        drive_folder_id=parsed.folder_id,
        scheduled_days=parsed.scheduled_days,
        dry_run=parsed.dry_run,
    )

    if parsed.status:
        orchestrator.status()
        return 0

    if parsed.sync:
        success = orchestrator.run_sync_only()
        return 0 if success else 1

    if parsed.render_only:
        orchestrator.run_render_only()
        return 0

    if parsed.auto:
        success = orchestrator.run_full()
        return 0 if success else 1

    return 0


if __name__ == "__main__":
    raise SystemExit(run())
