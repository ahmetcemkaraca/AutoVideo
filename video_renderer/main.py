#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main entry point for video renderer application.
"""

import json
import sys
import time
import traceback
import random
import subprocess
import os
import shutil
import uuid
from pathlib import Path
from typing import List, Tuple, Optional

# Fix: Ensure project root is in Python path for config imports
# This resolves the issue where files import from root `config/` which may not be in Python path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from . import __version__
from config import (
    RendererConfig as RenderConfig,
    VIDEO_EXTENSIONS,
    AUDIO_EXTENSIONS,
    get_best_encoder,
    detect_available_encoders,
    CODECS,
)
from .ffmpeg import FFmpegRunner, probe_video, get_duration, VideoInfo
from .video import VideoEncoder, encode_parallel
from .batch import SmartBatchDetector, BatchPair
from concurrent.futures import ThreadPoolExecutor
from .audio import (
    AudioProcessor,
    is_background_file,
    parse_background_gain_db,
    mux_video_audio,
    create_timed_effects_track,
)
from .validator import PostRenderValidator
from .tui import (
    console,
    print_header,
    print_working_directory,
    print_video_table,
    print_audio_table,
    print_video_info_panel,
    ask_text,
    ask_int,
    ask_choice,
    ask_confirm,
    ask_multiple_choice,
    print_summary,
    print_completion,
    print_success,
    print_error,
    print_warning,
    print_info,
    MultiStepProgress,
    ask_duration_components,
    BackNavigation,
)

# ═══════════════════════════════════════════════════════════════════════════════
# File Discovery
# ═══════════════════════════════════════════════════════════════════════════════


def check_ffmpeg_install() -> bool:
    """Check if ffmpeg and ffprobe are installed."""
    import shutil

    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")

    if not ffmpeg:
        from .tui import print_error, print_info

        print_error("FFmpeg bulunamadi!")
        print_info("Lutfen yukleyin: sudo apt install ffmpeg")
        return False

    if not ffprobe:
        from .tui import print_error, print_info

        print_error("FFprobe bulunamadi!")
        print_info("Lutfen yukleyin: sudo apt install ffmpeg")
        return False

    return True


def list_video_files(base: Path) -> List[Tuple[Path, VideoInfo]]:
    """List all mp4/mkv/etc files with their info, including final outputs."""
    files = []

    # Debug: List what we see
    from .tui import console

    # video_renderer/main.py içinde module level logger veya print kullanmak yerine
    # doğrudan console.print ile debug basalım ama tui.py bağımlılığı var.

    candidates = []
    for p in sorted(base.iterdir()):
        if not p.is_file():
            continue
        if p.suffix.lower() in VIDEO_EXTENSIONS:
            candidates.append(p)

    if not candidates:
        return []

    for p in candidates:
        try:
            info = probe_video(p)
            files.append((p, info))
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            FileNotFoundError,
            OSError,
        ) as e:
            # Print warning why this file failed
            # Use minimal print to avoid circular imports or messy logs
            print(f"UYARI: {p.name} okunamadi (ffprobe hatasi): {e}")
            pass

    return files


def list_audio_files(music_dir: Path) -> Tuple[List[Path], List[Path]]:
    """
    List audio files, separating tracks from backgrounds.
    Returns (tracks, backgrounds).
    """
    tracks = []
    backgrounds = []

    if not music_dir.exists():
        return tracks, backgrounds

    for p in sorted(music_dir.iterdir()):
        if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS:
            if is_background_file(p):
                backgrounds.append(p)
            else:
                tracks.append(p)

    return tracks, backgrounds


# ═══════════════════════════════════════════════════════════════════════════════
# Time Parsing
# ═══════════════════════════════════════════════════════════════════════════════


def parse_duration(s: str) -> int:
    """Parse HH:MM:SS to seconds."""
    import re

    s = s.strip()

    # HH:MM:SS format
    match = re.fullmatch(r"(\d{1,2}):([0-5]?\d):([0-5]?\d)", s)
    if match:
        h, m, s_val = map(int, match.groups())
        return h * 3600 + m * 60 + s_val

    # Just minutes:seconds (M:SS or MM:SS)
    match = re.fullmatch(r"(\d{1,3}):([0-5]?\d)", s)
    if match:
        m, s_val = map(int, match.groups())
        return m * 60 + s_val

    raise ValueError("Format HH:MM:SS veya MM:SS olmali (orn: 08:06:07 veya 30:00)")


def format_duration(seconds: int) -> str:
    """Format seconds to HH:MM:SS."""
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def create_run_tmp_dir(base: Path) -> Tuple[str, Path]:
    """Create isolated tmp directory for a single render run."""
    run_id = f"{time.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}_{uuid.uuid4().hex[:6]}"
    run_dir = base / "tmp" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_id, run_dir


def run_post_render_review_cli(out_path: Path, target_seconds: int, target_specs: dict) -> None:
    """Show post-render validation summary/detail before next action selection."""
    validator = PostRenderValidator()
    result = validator.validate_output(out_path, target_seconds, target_specs)

    def show_summary() -> None:
        console.print()
        console.print("[header]Render Sonrasi Kontrol (Ozet)[/]")
        console.print(f"  Durum: {'[success]Uygun[/]' if result.valid else '[error]Sorunlu[/]'}")
        console.print(
            f"  Hata/Uyari/Bilgi: {len(result.errors)}/{len(result.warnings)}/{len(result.info)}"
        )
        output_meta = result.metadata.get("output", {})
        youtube_meta = result.metadata.get("youtube", {})
        if output_meta:
            console.print(
                f"  Cikti: {output_meta.get('codec', '-')} | {output_meta.get('width', '-')}x{output_meta.get('height', '-')} | {output_meta.get('fps', '-')}"
            )
            console.print(
                f"  Sure: hedef={output_meta.get('target_duration', '-')}s, gercek={float(output_meta.get('duration', 0)):.1f}s"
            )
        if youtube_meta:
            console.print(
                f"  YouTube: {youtube_meta.get('format_name', '-')} | v={youtube_meta.get('video_codec', '-')} | a={youtube_meta.get('audio_codec', '-')}"
            )

    def show_detail() -> None:
        console.print()
        console.print("[header]Render Sonrasi Kontrol (Detay)[/]")
        if not result.issues:
            console.print("  [success]Sorun bulunmadi.[/]")
            return
        for issue in result.issues:
            sev = issue.severity.value.upper()
            console.print(f"  [{sev}] ({issue.category}) {issue.message}")
            if issue.details:
                console.print(f"    - {issue.details}")
            if issue.suggestion:
                console.print(f"    - Oneri: {issue.suggestion}")

    show_summary()
    while True:
        c = ask_choice("Kontrol secenegi", ["Devam et", "Detay goster", "Ozeti tekrar goster"], 1)
        if c == 1:
            break
        if c == 2:
            show_detail()
        elif c == 3:
            show_summary()


# ═══════════════════════════════════════════════════════════════════════════════
# Resume Support
# ═══════════════════════════════════════════════════════════════════════════════


def run_resume() -> int:
    """Resume from last session."""
    base = Path.cwd()
    session_json = base / "tmp" / "last_session.json"

    print_header()
    print_working_directory(base)

    if not session_json.exists():
        print_error("Devam edilecek session bulunamadi!")
        print_info("Once normal render baslatin, sonra --resume kullanin.")
        return 2

    try:
        session = json.loads(session_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, IOError) as e:
        print_error(f"Session dosyasi okunamadi: {e}")
        return 2

    tmp_dir = Path(session.get("tmp_dir", (base / "tmp").as_posix()))
    tmp_dir.mkdir(parents=True, exist_ok=True)
    run_log = tmp_dir / "run_log.txt"
    err_log = tmp_dir / "error_log.txt"

    # Load session data
    mode = session.get("mode", "intro_loop")
    intro_path = Path(session["intro"]) if mode != "single" else None
    loop_path = Path(session["loop"]) if mode != "single" else None
    single_video_path = Path(session["video"]) if mode == "single" else None
    codec_family = session["codec"]
    codec_config = get_best_encoder(codec_family)
    total_seconds = session["duration_sec"]
    dur_str = session["duration"]
    chosen_tracks = [Path(p) for p in session["tracks"]]
    tracks_validated = session.get("tracks_validated", False)
    chosen_bgs = [(Path(b["path"]), b["db"]) for b in session.get("bgs", [])]
    timed_effects = session.get("timed_effects", [])
    out_path = Path(session["out"])
    out_path = Path(session["out"])
    post_action = session.get("post_action", "keep")

    # Load advanced config
    config = session.get("config", {})
    target_width = config.get("width", 1920)
    target_height = config.get("height", 1080)
    target_fps = config.get("fps", 60.0)
    scale_algo = config.get("scale_algo", "lanczos")
    audio_bitrate = config.get("audio_bitrate", "192k")
    drive_enabled = config.get("drive_enabled", False)
    drive_folder_id = config.get("drive_folder_id", "")
    video_audio_mode = config.get("video_audio_mode", "keep")
    keep_video_audio = video_audio_mode == "keep"
    apply_audio_fades = bool(config.get("apply_audio_fades", False))
    audio_fade_in_sec = float(config.get("audio_fade_in_sec", 5.0))
    audio_fade_out_sec = float(config.get("audio_fade_out_sec", 15.0))

    print_success(f"Session bulundu: {session['ts']}")
    print_info(f"Hedef: {out_path.name} ({dur_str})")
    print_info(
        f"Ayarlar: {target_width}x{target_height} @ {target_fps} fps | {scale_algo} | {audio_bitrate}"
    )

    # Define output paths for each step
    intro_norm = tmp_dir / f"intro_norm_{codec_family}.mp4"
    loop_norm = tmp_dir / f"loop_norm_{codec_family}.mp4"
    video_only_single = tmp_dir / f"video_only_single_{codec_family}.mp4"
    video_only_pattern = tmp_dir / "video_only_*.mp4"
    music_loop = tmp_dir / "music_loop.w64"
    audio_mixed = tmp_dir / "audio_mixed.w64"

    try:
        runner = FFmpegRunner(run_log)

        steps = ["Intro encode", "Loop encode", "Video concat", "Audio isleme", "Final mux"]

        console.print()

        with MultiStepProgress(steps) as progress:

            encoder = VideoEncoder(
                runner=runner,
                codec_config=codec_config,
                width=target_width,
                height=target_height,
                fps=target_fps,
            )

            def make_progress_callback(step_idx: int):
                # Print step name, return None so FFmpeg shows raw terminal output
                step_name = steps[step_idx] if step_idx < len(steps) else "?"
                console.print(f"\n[bold cyan]▶ [{step_idx+1}/{len(steps)}] {step_name}[/bold cyan]")
                return None

            # Step 1-3: Video processing
            if mode == "single" and single_video_path:
                if total_seconds <= 0:
                    total_seconds = int(get_duration(single_video_path))
                if video_only_single.exists():
                    video_only = video_only_single
                    print_info("Tek video encode zaten var, atlaniyor...")
                else:
                    video_only = encoder.normalize_video(
                        single_video_path,
                        video_only_single,
                        make_progress_callback(0),
                        scale_algo=scale_algo,
                    )
                progress.complete_step(0)
                progress.complete_step(1)
                progress.complete_step(2)
            else:
                # Step 1: Encode intro (skip if exists)
                if intro_norm.exists():
                    print_info(f"Intro zaten encode edilmis, atlaniyor...")
                    progress.complete_step(0)
                else:
                    encoder.normalize_video(
                        intro_path, intro_norm, make_progress_callback(0), scale_algo=scale_algo
                    )
                    progress.complete_step(0)

                # Step 2: Encode loop (skip if exists)
                if loop_norm.exists():
                    print_info(f"Loop zaten encode edilmis, atlaniyor...")
                    progress.complete_step(1)
                else:
                    encoder.normalize_video(
                        loop_path, loop_norm, make_progress_callback(1), scale_algo=scale_algo
                    )
                    progress.complete_step(1)

                # Step 3: Concat (check for video_only file)
                video_only_files = list(tmp_dir.glob("video_only_*.mp4"))
                if video_only_files:
                    video_only = video_only_files[0]
                    print_info(f"Video concat zaten yapilmis, atlaniyor...")
                    progress.complete_step(2)
                else:
                    video_only = encoder.concat_videos(
                        intro_norm, loop_norm, total_seconds, tmp_dir, make_progress_callback(2)
                    )
                    progress.complete_step(2)

            # Step 4: Audio (check for music_loop or audio_mixed)
            audio_processor = AudioProcessor(runner, tmp_dir)

            if chosen_bgs and audio_mixed.exists():
                audio_full = audio_mixed
                print_info(f"Audio zaten islenmis, atlaniyor...")
                progress.complete_step(3)
            elif not chosen_bgs and music_loop.exists():
                audio_full = music_loop
                print_info(f"Audio zaten islenmis, atlaniyor...")
                progress.complete_step(3)
            else:
                music_loop_file = audio_processor.create_music_loop(
                    chosen_tracks, total_seconds, pre_validated=tracks_validated
                )

                if chosen_bgs:
                    bg_processed = audio_processor.process_backgrounds(chosen_bgs)
                    audio_full = audio_processor.mix_tracks(
                        music_loop_file, bg_processed, total_seconds
                    )
                else:
                    audio_full = music_loop_file

                if timed_effects:
                    effects_track = create_timed_effects_track(
                        runner, tmp_dir, timed_effects, total_seconds
                    )
                    if effects_track and effects_track.exists():
                        audio_full = audio_processor.mix_tracks(
                            audio_full, [effects_track], total_seconds
                        )

                progress.complete_step(3)

            # Step 5: Final mux (always run if output doesn't exist)
            if out_path.exists():
                print_info(f"Final dosya zaten var, atlaniyor...")
                progress.complete_step(4)
            else:
                mux_video_audio(
                    runner,
                    video_only,
                    audio_full,
                    out_path,
                    audio_bitrate=audio_bitrate,
                    progress_callback=make_progress_callback(4),
                    keep_video_audio=keep_video_audio,
                    apply_audio_fades=apply_audio_fades,
                    fade_in_sec=audio_fade_in_sec,

                    fade_out_sec=audio_fade_out_sec,
                )
                progress.complete_step(4)

        # Completion
        final_duration = get_duration(out_path)
        print_completion(out_path, final_duration)

        # CLEANUP before review (except final output)
        try:
            for f in tmp_dir.glob("*"):
                if f.is_file() and f != out_path:
                    f.unlink(missing_ok=True)
        except Exception:
            pass

        run_post_render_review_cli(
            out_path,
            total_seconds,
            {
                "codec": codec_family,
                "width": target_width,
                "height": target_height,
                "fps": target_fps,
                "has_audio": True,
            },
        )


        # Post action
        if post_action == "delete":
            try:
                if mode == "single" and single_video_path:
                    single_video_path.unlink(missing_ok=True)
                    print_success("Kaynak video silindi.")
                else:
                    intro_path.unlink(missing_ok=True)
                    loop_path.unlink(missing_ok=True)
                    print_success("Kaynak intro/loop silindi.")
            except Exception as e:
                print_warning(f"Kaynak silme hatasi: {e}")

        elif post_action == "archive":
            archive_dir = base / "archive" / time.strftime("%Y%m%d_%H%M%S")
            archive_dir.mkdir(parents=True, exist_ok=True)
            try:
                if mode == "single" and single_video_path:
                    if single_video_path.exists():
                        single_video_path.rename(archive_dir / single_video_path.name)
                    print_success(f"Kaynak video arsivlendi: {archive_dir.as_posix()}")
                else:
                    if intro_path.exists():
                        intro_path.rename(archive_dir / intro_path.name)
                    if loop_path.exists():
                        loop_path.rename(archive_dir / loop_path.name)
                    print_success(f"Kaynak intro/loop arsivlendi: {archive_dir.as_posix()}")
            except Exception as e:
                print_warning(f"Arsivleme hatasi: {e}")

        # ──────────────────────────────────────────────────────────────
        # Drive Upload
        # ──────────────────────────────────────────────────────────────
        if drive_enabled:
            console.print()
            print_info("Google Drive'a yukleniyor...")

            try:
                from .drive import DriveUploader

                uploader = DriveUploader()
                success, file_id = uploader.upload_file(
                    out_path, drive_folder_id if drive_folder_id else None
                )
                if success:
                    print_success(f"Video basariyla yuklendi! ID: {file_id}")
                else:
                    print_error(f"Yukleme basarisiz: {file_id}")
            except Exception as e:
                print_error(f"Upload hatasi: {e}")

        return 0

    except KeyboardInterrupt:
        console.print()
        print_warning("Kullanici tarafindan iptal edildi.")
        return 130

    except Exception as e:
        tb = traceback.format_exc()
        msg = f"# ERROR — {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n{tb}\n"
        err_log.write_text(msg, encoding="utf-8")

        console.print()
        print_error(f"Hata olustu: {e}")
        print_info(f"Detaylar: {err_log.as_posix()}")
        print_info("Hatayi duzelttikten sonra --resume ile devam edebilirsiniz.")
        return 4


# ═══════════════════════════════════════════════════════════════════════════════
# Smart Batch Mode
# ═══════════════════════════════════════════════════════════════════════════════


def run_batch() -> int:
    """
    Smart Batch mode - Otomatik intro/loop çiftlerini tespit et ve sıralı render yap.
    """
    from .batch import SmartBatchDetector, BatchPair

    base = Path.cwd()
    music_dir = base / "music"
    tmp_dir = base / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    try:
        print_header()
        console.print("\n[bold cyan]═══════════════════════════════════════════════════════════[/]")
        console.print("[bold cyan]                  SMART BATCH MODE                         [/]")
        console.print("[bold cyan]═══════════════════════════════════════════════════════════[/]\n")

        # Scan for intro/loop pairs
        detector = SmartBatchDetector(base)
        pairs = detector.scan()

        if not pairs:
            print_error("Bu klasörde intro/loop çifti bulunamadı!")
            print_info("Dosya adları şu formatta olmalı: *_intro.mp4 ve *_loop.mp4")
            return 1

        # Display detected pairs
        console.print(f"\n[success]✓ {len(pairs)} adet intro/loop çifti bulundu:[/]\n")
        # Confirmaton removed as requested


        # Check music directory
        music_candidates = [base / "music", base / "Music"]
        for candidate in music_candidates:
            if candidate.exists() and candidate.is_dir():
                music_dir = candidate
                break

        if not music_dir.exists():
            print_error("music/ klasörü bulunamadı!")
            return 2

        # Get shared settings for all batches
        console.print("\n[header]Tüm renderlar için ortak ayarlar:[/]\n")

        # Codec selection
        from config import CODECS

        codec_names = list(CODECS.keys())
        codec_display = [f"{name} ({CODECS[name].name})" for name in codec_names]
        codec_idx = ask_choice("Codec seçin", codec_display, 1)
        codec_family = codec_names[codec_idx - 1]
        codec_config = CODECS[codec_family]

        # Duration
        console.print()
        dur_options = ["8:00:00", "9:00:00", "10:00:00", "Rastgele (8-10 saat)", "Özel"]
        dur_idx = ask_choice("Video süresi", dur_options, 2)

        if dur_idx == 4:
            import random

            total_seconds = random.randint(28800, 36000)
            dur_str = f"{total_seconds // 3600}:{(total_seconds % 3600) // 60:02d}:{total_seconds % 60:02d}"
        elif dur_idx == 5:
            dur_str = ask_text("Süre (H:MM:SS)", "9:00:00")
            total_seconds = parse_time(dur_str)
        else:
            dur_str = dur_options[dur_idx - 1]
            total_seconds = parse_time(dur_str)

        # Get music tracks (exclude background files)
        console.print()
        track_exts = (".mp3", ".wav", ".flac", ".ogg", ".m4a")
        # Filter: audio files that are NOT background files
        tracks = sorted([f for f in music_dir.iterdir()
                        if f.suffix.lower() in track_exts and not is_background_file(f)])

        if not tracks:
            print_error("music/ klasöründe müzik dosyası bulunamadı!")
            return 2

        console.print(f"[info]Müzik klasöründe {len(tracks)} track bulundu.[/]")
        
        # MUSIC SELECTION
        music_mode = ask_choice(
            "Muzik Secimi", 
            [
                "Rastgele (Her video farkli)", 
                "Sirali (Dosya adi)", 
                "Manuel Secim",
                "Muzik Yok"
            ], 
            2
        )
        
        global_tracks = []
        if music_mode == 2: # Sorted
            global_tracks = sorted(tracks)
        elif music_mode == 3: # Manual
            # Fix: map indices back to tracks
            selected_indices = ask_multiple_choice(
                "Muzikleri secin", 
                [t.name for t in tracks],
                min_count=1
            )
            global_tracks = [tracks[i-1] for i in selected_indices]
        elif music_mode == 4: # None
            global_tracks = []

        # Source Audio Option
        # User wants source audio kept by default sometimes, ask preference
        keep_source_audio = ask_confirm("Kaynak videonun orijinal sesi korunsun mu?", False)


        # Background audio (optional)
        console.print()
        chosen_bgs = []
        if ask_confirm("Arka plan sesi eklemek ister misiniz?", False):
            # Collect bg files from both background/ directory and music/ directory
            bg_files_list = []

            # Check background/ directory first
            bg_audio = base / "background"
            if bg_audio.exists():
                bg_files_list.extend([f for f in bg_audio.iterdir() if f.suffix.lower() in track_exts])

            # Also check music/ directory for bg files (files starting with "bg" or containing "_bg_")
            bg_from_music = sorted([f for f in music_dir.iterdir()
                                   if f.suffix.lower() in track_exts and is_background_file(f)])
            bg_files_list.extend(bg_from_music)

            # Remove duplicates (by name) and sort
            bg_files = sorted({bg.name: bg for bg in bg_files_list}.values())

            if bg_files:
                for bg in bg_files:
                    console.print(f"  [muted]- {bg.name}[/]")
                bg_gain = ask_text("Arka plan gain (dB, örn: -13)", "-13")
                try:
                    bg_gain_db = float(bg_gain)
                except ValueError:
                    bg_gain_db = -13.0
                chosen_bgs = [(bg, bg_gain_db) for bg in bg_files]

        # Summary
        console.print("\n[header]Batch Özeti:[/]")
        console.print(f"  [bold]Çift sayısı:[/] {len(pairs)}")
        console.print(f"  [bold]Codec:[/] {codec_family}")
        console.print(f"  [bold]Süre:[/] {dur_str} ({total_seconds} saniye)")
        console.print(f"  [bold]Müzik Modu:[/] {['Rastgele', 'Sirali', 'Manuel', 'Yok'][music_mode-1]}")
        console.print(f"  [bold]Arka plan:[/] {len(chosen_bgs)} dosya")
        console.print(f"  [bold]Kaynak Ses:[/] {'Evet' if keep_source_audio else 'Hayir'}")
        console.print()

        # Post Render Action
        post_action_idx = ask_choice(
            "Islem tamamlandiginda kaynak dosyalar ne olsun?",
            ["Hicbir sey yapma (Kalsin)", "Arsivle (archive/ klasorune tasi)", "Sil"],
            2
        )
        post_action_map = {1: "keep", 2: "archive", 3: "delete"}
        post_action = post_action_map[post_action_idx]
        
        # Audio fade defaults
        audio_fade_in = 5.0
        audio_fade_out = 15.0
        apply_fades = ask_confirm(f"Fade efekti uygulansin mi? (In: {audio_fade_in}s, Out: {audio_fade_out}s)", False)


        if not ask_confirm("Batch render başlatılsın mı?", True):
             # Just proceed, user complained about redundancy
             pass 


        # ═══════════════════════════════════════════════════════════════
        # Execute batch renders sequentially
        # ═══════════════════════════════════════════════════════════════

        results = []
        total_start = time.perf_counter()

        for i, pair in enumerate(pairs, 1):
            console.print()
            console.print("=" * 60)
            console.print(f"[bold cyan]BATCH [{i}/{len(pairs)}] - {pair.name}[/]")
            console.print("=" * 60)

            # Clean tmp for each render
            for f in tmp_dir.glob("*.mp4"):
                f.unlink(missing_ok=True)
            for f in tmp_dir.glob("*.w64"):
                f.unlink(missing_ok=True)

            # Create output name
            out_name = f"final_{pair.name}_{codec_family}.mp4"
            out_path = base / out_name

            try:
                # Setup encoder
                runner_video = FFmpegRunner(tmp_dir / "run_log_video.txt")
                runner_audio = FFmpegRunner(tmp_dir / "run_log_audio.txt")
                
                audio_processor = AudioProcessor(runner_audio, tmp_dir)
                encoder = VideoEncoder(
                    runner=runner_video, codec_config=codec_config, width=1920, height=1080, fps=60
                )

                intro_norm = tmp_dir / f"intro_norm_{codec_family}.mp4"
                loop_norm = tmp_dir / f"loop_norm_{codec_family}.mp4"

                # Parallel encode + audio
                from concurrent.futures import ThreadPoolExecutor

                video_only = None
                audio_full = None

                def encode_video():
                    nonlocal video_only
                    encoder.normalize_video(pair.intro, intro_norm, None, keep_audio=keep_source_audio)
                    encoder.normalize_video(pair.loop, loop_norm, None, keep_audio=keep_source_audio)
                    video_only = encoder.concat_videos(
                        intro_norm, loop_norm, total_seconds, tmp_dir, None, keep_audio=keep_source_audio
                    )
                    return video_only

                def process_audio():
                    nonlocal audio_full
                    
                    # Determine tracks for this job
                    job_tracks = []
                    if music_mode == 1: # Random
                         # Shuffle local copy
                         import random
                         shuffled = list(tracks)
                         random.shuffle(shuffled)
                         job_tracks = shuffled
                    else: # Sorted, Manual (Global), or None
                         job_tracks = global_tracks

                    if not job_tracks:
                        # If no music, return None (muxer will handle just video audio if present)
                        # But wait, create_music_loop might fail with empty list
                        # If bg exists, we still need audio chain
                        pass

                    if job_tracks:
                        music_loop = audio_processor.create_music_loop(job_tracks, total_seconds)
                        if chosen_bgs:
                            bg_processed = audio_processor.process_backgrounds(chosen_bgs)
                            audio_full = audio_processor.mix_tracks(
                                music_loop, bg_processed, total_seconds
                            )
                        else:
                            audio_full = music_loop
                    elif chosen_bgs:
                         # Only BG
                         # We need a silent base or just mix BGs? 
                         # AudioProcessor.mix_tracks expects main_track. 
                         # Let's create silent base if no music but BGs
                         # For now assuming user picks music if they pick BG, or just use first BG as base?
                         # Simplest: Just use first BG as base and mix others
                         bg_processed = audio_processor.process_backgrounds(chosen_bgs)
                         if bg_processed:
                            audio_full = bg_processed[0]
                            if len(bg_processed) > 1:
                                audio_full = audio_processor.mix_tracks(audio_full, bg_processed[1:], total_seconds)
                    else:
                        audio_full = None

                    return audio_full


                with ThreadPoolExecutor(max_workers=2) as executor:
                    video_future = executor.submit(encode_video)
                    audio_future = executor.submit(process_audio)
                    video_only = video_future.result()
                    audio_full = audio_future.result()

                # Final mux
                # If audio_full is None (no music/bg), mux_video_audio handles it (uses video audio if present)
                if audio_full is None:
                     # Create silence
                     silence_path = tmp_dir / "silence.w64"
                     subprocess.run([
                         "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", 
                         "-t", str(total_seconds), "-c:a", "pcm_s16le", "-f", "w64", str(silence_path)
                     ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                     audio_full = silence_path

                time.sleep(0.5) # Allow handles to close
                mux_runner = FFmpegRunner(tmp_dir / "run_log_mux.txt")
                mux_video_audio(
                    mux_runner, video_only, audio_full, out_path, 
                    keep_video_audio=keep_source_audio,
                    apply_audio_fades=apply_fades,
                    fade_in_sec=audio_fade_in,
                    fade_out_sec=audio_fade_out
                )

                print_success(f"[{i}/{len(pairs)}] {pair.name} tamamlandı: {out_path.name}")
                results.append((pair.name, True, out_path))
            
                # ════════════════════════════════════════════════════════════════════
                # MOVED OUTSIDE EXECUTOR/TRY CONTEXT (DEDENTED) -> Actually keeping inside try for safety
                # ════════════════════════════════════════════════════════════════════
                
                # Metadata / Archive logic
                try:
                    meta = {
                        "source": pair.name,
                        "intro": pair.intro.name,
                        "loop": pair.loop.name,
                        "codec": codec_family,
                        "duration": total_seconds,
                        "music_mode": music_mode,
                        "music_tracks": [t.name for t in (job_tracks if 'job_tracks' in locals() else [])],
                        "keep_source_audio": keep_source_audio,
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    
                    if post_action == "archive":
                        archive_dir = base / "archive" # Shared archive root
                        job_archive = archive_dir / f"{time.strftime('%Y%m%d')}_{pair.name}"
                        job_archive.mkdir(parents=True, exist_ok=True)
                        
                        # Move sources
                        if pair.intro.exists():
                            shutil.move(str(pair.intro), str(job_archive / pair.intro.name))
                        if pair.loop.exists():
                            shutil.move(str(pair.loop), str(job_archive / pair.loop.name))
                            
                        # Save meta
                        (job_archive / "render_info.json").write_text(json.dumps(meta, indent=2))
                        print_success(f"  Arsivlendi: {job_archive.name}")
                        
                    elif post_action == "delete":
                        if pair.intro.exists(): pair.intro.unlink()
                        if pair.loop.exists(): pair.loop.unlink()
                        print_success("  Kaynak dosyalar silindi.")
                        
                    # Save meta to logs
                    log_archive = base / "archive" / "logs"
                    log_archive.mkdir(parents=True, exist_ok=True)
                    (log_archive / f"meta_{out_path.stem}.json").write_text(json.dumps(meta, indent=2))
                    
                except Exception as e:
                    print_warning(f"Islem sonrasi hata: {e}")
                
                # Final cleanup of tmp (audio/video segments)
                for f in tmp_dir.glob("*"):
                     if f.is_file() and f != out_path and f.suffix.lower() not in ['.txt', '.log']: # Keep logs
                         try: f.unlink()
                         except: pass




            except Exception as e:
                print_error(f"[{i}/{len(pairs)}] {pair.name} HATA: {e}")
                results.append((pair.name, False, str(e)))

        # Summary
        total_time = time.perf_counter() - total_start
        console.print()
        console.print("=" * 60)
        console.print("[bold green]BATCH TAMAMLANDI[/]")
        console.print("=" * 60)

        success_count = sum(1 for _, ok, _ in results if ok)
        console.print(f"[bold]Başarılı:[/] {success_count}/{len(pairs)}")
        console.print(f"[bold]Toplam süre:[/] {int(total_time // 60)}m {int(total_time % 60)}s")

        for name, ok, path in results:
            if ok:
                console.print(f"  [success]✓[/] {name}: {path.name}")
            else:
                console.print(f"  [error]✗[/] {name}: {path}")

        return 0

    except KeyboardInterrupt:
        print_warning("\nBatch kullanıcı tarafından iptal edildi.")
        return 130
    except Exception as e:
        import traceback

        print_error(f"Batch hatası: {e}")
        traceback.print_exc()
        return 4


# ═══════════════════════════════════════════════════════════════════════════════
# Interactive Wizard - Helper Functions
# ═══════════════════════════════════════════════════════════════════════════════


def select_render_mode(videos: List[Tuple[Path, VideoInfo]]) -> str:
    """
    Let user select render mode.

    Args:
        videos: List of available video files with their info

    Returns:
        "intro_loop" for intro+loop mode, "single" for single video mode
    """
    mode_idx = ask_choice("Render modu", ["Intro + Loop", "Tek Video (sesi degistir)"], 1)
    return "intro_loop" if mode_idx == 1 else "single"


def select_videos_for_mode(
    mode: str, videos: List[Tuple[Path, VideoInfo]]
) -> Tuple[Optional[Path], Optional[Path], Optional[Path]]:
    """
    Select video files based on render mode.

    Args:
        mode: Render mode ("intro_loop" or "single")
        videos: List of available video files with their info

    Returns:
        Tuple of (intro_path, loop_path, single_video_path)
        Paths that are not relevant to the mode will be None
    """
    intro_path = None
    loop_path = None
    single_video_path = None

    if mode == "single":
        single_idx = ask_int("VIDEO hangisi?", 1, len(videos))
        single_video_path, single_info = videos[single_idx - 1]
        print_video_info_panel("VIDEO", single_video_path, single_info)
    else:
        # Select intro/loop
        intro_idx = ask_int("INTRO hangisi?", 1, len(videos))
        loop_idx = ask_int("LOOP hangisi?", 1, len(videos))

        if intro_idx == loop_idx:
            print_error("Intro ve loop ayni dosya olamaz!")
            raise ValueError("Intro and loop cannot be the same file")

        intro_path, intro_info = videos[intro_idx - 1]
        loop_path, loop_info = videos[loop_idx - 1]

        # Show detailed info
        print_video_info_panel("INTRO", intro_path, intro_info)
        print_video_info_panel("LOOP", loop_path, loop_info)

    return intro_path, loop_path, single_video_path


def get_output_filename(
    mode: str, single_video_path: Optional[Path], codec_family: str, dur_str: str
) -> Path:
    """
    Get output filename from user or generate default.

    Args:
        mode: Render mode ("intro_loop" or "single")
        single_video_path: Path to single video (if single mode)
        codec_family: Codec family name
        dur_str: Formatted duration string

    Returns:
        Resolved Path object for output file
    """
    console.print()
    base = Path.cwd()

    if mode == "single" and single_video_path:
        base_name = single_video_path.stem
        default_out = f"final_{base_name}_{codec_family}.mp4"
    else:
        default_out = f"final_{codec_family}_{dur_str.replace(':', 'h', 1).replace(':', 'm')}s.mp4"

    out_name = ask_text("Cikti dosyasi adi", default_out)

    # Sanitize filename (Fix for user copy-paste errors)
    import re

    safe_name = re.sub(r"[^\w\-. ]", "", out_name).strip()
    if not safe_name:
        safe_name = "output.mp4"
    if not safe_name.lower().endswith(".mp4"):
        safe_name += ".mp4"

    if safe_name != out_name:
        print_warning(f"Dosya adi duzeltildi: '{out_name}' -> '{safe_name}'")
        out_name = safe_name

    return (base / out_name).resolve()


# ═══════════════════════════════════════════════════════════════════════════════
# Interactive Wizard
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# Configuration Mode Functions
# ═══════════════════════════════════════════════════════════════════════════════


def configure_render_settings(
    mode: str,
    intro_path: Optional[Path],
    loop_path: Optional[Path],
    single_video_path: Optional[Path],
) -> Tuple:
    """
    Configure render settings based on user-selected mode.

    Returns:
        Tuple of (codec_family, codec_config, target_width, target_height, target_fps, scale_algo, audio_bitrate)
    """
    console.print()
    config_mode_idx = ask_choice(
        "Ayarlar Modu",
        [
            "[green]Basit[/] (Otomatik 1080p @ 60fps, Standart Kalite)",
            "[blue]Orta[/] (Cozunurluk Secimi, Otomatik Upscale)",
            "[yellow]Gelismis[/] (Cozunurluk, FPS, Upscale Metodu, Preset)",
            "[red]Ozel[/] (Her seyi elle ayarla)",
        ],
        1,
    )

    # Default Settings
    target_width = 1920
    target_height = 1080
    target_fps = 60
    scale_algo = "lanczos"
    audio_bitrate = "192k"

    available_encoders = detect_available_encoders()
    hw_available = any(available_encoders.values())

    if config_mode_idx == 1:  # Basit
        # Force Defaults: 1080p, 60fps, Native Codec (if possible), Lanczos
        print_info("Basit Mod: Otomatik analiz yapiliyor...")

        # Check source resolution to avoid unnecessary re-encode/resize
        smart_res_found = False

        if mode == "single" and single_video_path:
            try:
                ref_info = probe_video(single_video_path)
                target_width, target_height = ref_info.width, ref_info.height
                target_fps = (
                    float(ref_info.fps.split("/")[0]) / float(ref_info.fps.split("/")[1])
                    if "/" in ref_info.fps
                    else float(ref_info.fps)
                )
                smart_res_found = True
                print_success(
                    f"Kaynak cozunurlugu kullanilacak: {target_width}x{target_height} @ {target_fps:.2f}fps"
                )
            except Exception as e:
                print_warning(f"Video analiz hatasi: {e}. Varsayilan 1080p60 kullaniliyor.")

        elif mode == "intro_loop" and intro_path and loop_path:
            try:
                i_info = probe_video(intro_path)
                l_info = probe_video(loop_path)

                if i_info.width == l_info.width and i_info.height == l_info.height:
                    target_width, target_height = i_info.width, i_info.height
                    smart_res_found = True
                    print_success(
                        f"Intro/Loop cozunurlugu eslesiyor: {target_width}x{target_height}. Resize yapilmadi."
                    )
                else:
                    print_info("Intro ve Loop cozunurlukleri farkli. 1080p standardi uygulaniyor.")
            except Exception as e:
                print_warning(f"Analiz hatasi: {e}")

        if not smart_res_found:
            print_info("Varsayilan 1080p60 ayarlari uygulaniyor.")

        # Codec Detection (Native/Passthrough attempt)
        detected_codec = "av1" # Default fallback
        
        try:
            ref_path = single_video_path if mode == "single" else intro_path
            if ref_path and ref_path.exists():
                info = probe_video(ref_path)
                c_name = info.codec.lower()
                
                if "av1" in c_name:
                    detected_codec = "av1"
                elif "hevc" in c_name or "h265" in c_name:
                    detected_codec = "h265"
                elif "h264" in c_name or "avc" in c_name:
                    detected_codec = "h264"
                
                print_info(f"Kaynak codec: {c_name} -> Hedef: {detected_codec}")
        except Exception as e:
            print_warning(f"Codec tespit hatasi: {e}")

        codec_family = detected_codec
        # Fallback if AV1 HW invalid? get_best_encoder handles it.
        codec_config = get_best_encoder(codec_family)
        print_info(f"Encoder: {codec_config.name}")

    else:
        # Codec selection for Orta/Gelismis/Ozel
        codec_options = [
            "AV1 (YouTube 1080p Premium master)",
            "H.264 (hizli encode, genis uyumluluk)",
            "H.265/HEVC (yuksek sikistirma)",
        ]
        if hw_available:
            hw_list = [k for k, v in available_encoders.items() if v]
            print_success(f"Hardware acceleration mevcut: {', '.join(hw_list)}")

        codec_idx = ask_choice("Hedef codec", codec_options, 1)
        codec_family = ["av1", "h264", "h265"][codec_idx - 1]
        codec_config = get_best_encoder(codec_family)

        # Mode Logic
        if config_mode_idx == 2:  # Orta
            # Ask Resolution only
            res_choice = ask_choice(
                "Cozunurluk",
                ["1080p (Full HD)", "1440p (2K)", "2160p (4K)", "Kaynak Cozunurlugu"],
                1,
            )
            if res_choice == 1:
                target_width, target_height = 1920, 1080
            elif res_choice == 2:
                target_width, target_height = 2560, 1440
            elif res_choice == 3:
                target_width, target_height = 3840, 2160
            elif res_choice == 4:
                ref_path = single_video_path if mode == "single" else intro_path
                ref_info = probe_video(ref_path)
                target_width, target_height = ref_info.width, ref_info.height

            print_info("Orta Mod: Diger ayarlar otomatik (60fps, Lanczos, 192k).")

        elif config_mode_idx >= 3:  # Gelismis / Ozel
            # Resolution
            res_choice = ask_choice(
                "Cozunurluk", ["1080p", "1440p", "2160p", "Kaynak", "Manuel Gir"], 1
            )
            if res_choice == 1:
                target_width, target_height = 1920, 1080
            elif res_choice == 2:
                target_width, target_height = 2560, 1440
            elif res_choice == 3:
                target_width, target_height = 3840, 2160
            elif res_choice == 4:
                ref_path = single_video_path if mode == "single" else intro_path
                ref_info = probe_video(ref_path)
                target_width, target_height = ref_info.width, ref_info.height
            elif res_choice == 5:
                target_width = ask_int("Genislik (px)", 100, 7680, 1920)
                target_height = ask_int("Yukseklik (px)", 100, 4320, 1080)

            # FPS
            fps_choice = ask_choice("FPS", ["60", "30", "24", "Kaynak"], 1)
            if fps_choice == 1:
                target_fps = 60
            elif fps_choice == 2:
                target_fps = 30
            elif fps_choice == 3:
                target_fps = 24
            elif fps_choice == 4:
                ref_path = single_video_path if mode == "single" else intro_path
                ref_info = probe_video(ref_path)
                target_fps = (
                    float(ref_info.fps.split("/")[0]) / float(ref_info.fps.split("/")[1])
                    if "/" in ref_info.fps
                    else float(ref_info.fps)
                )

            # Upscale Algo
            scale_algo = ask_choice(
                "Upscale Algoritmasi",
                [
                    "lanczos (Keskin/High Qual)",
                    "bicubic (Standart)",
                    "bilinear (Hizli)",
                    "spline (Yumusak)",
                ],
                1,
            )
            scale_algo = ["lanczos", "bicubic", "bilinear", "spline"][scale_algo - 1]

            # Audio Bitrate
            audio_bitrate = ask_choice(
                "Audio Bitrate", ["128k", "192k (Standart)", "256k", "320k (Yuksek)"], 2
            )
            audio_bitrate = ["128k", "192k", "256k", "320k"][audio_bitrate - 1]

            if config_mode_idx == 4:  # Ozel
                # Ask about editing the command/header?
                if ask_confirm("Varsayilan FFmpeg parametrelerini duzenlemek ister misiniz?"):
                    print_info("Not: Bu ozellik su anki surumde komut satirina yansitilacaktir.")
                    codec_config.preset = ask_text(
                        f"Preset ({codec_config.preset})", codec_config.preset
                    )
                    crf_val = ask_int(f"CRF/CQ ({codec_config.crf})", 0, 51, codec_config.crf)
                    codec_config.crf = crf_val

    # ──────────────────────────────────────────────────────────────
    # NEW: Bitrate Selection
    # ──────────────────────────────────────────────────────────────
    console.print()
    video_bitrate = None
    
    # Kendi yazabileyim veya kaynak
    # "Basit" modda istense de, genel olarak sormak mantikli mi?
    # Kullanici "CLI modda basit seceneklerde" dedi.
    # We'll ask if user wants to override bitrate.
    
    use_custom_bitrate = ask_choice(
        "Video Bitrate (Kalite)",
        [
            "Otomatik (Varsayilan/CRF)", 
            "Ozel Bitrate Gir (kbps/M)",
            "Kaynak Video Bitrate'ini Kopyala (Deneysel)"
        ],
        1
    )
    
    if use_custom_bitrate == 2:
        video_bitrate = ask_text("Bitrate (orn: 5M, 5000k)", "5M")
    elif use_custom_bitrate == 3:
        # Try to detect source setup
        ref_path = single_video_path if mode == "single" else intro_path
        if ref_path and ref_path.exists():
             try:
                 # We don't have bitrate in probe result easily here without parsing again or trusting info
                 # Let's just ask user to confirm source bitrate or just pass a flag?
                 # Encoder supports string bitrate.
                 # If we return "auto", it uses deafult.
                 # If we want source, we might need to extract it.
                 # Let's try to extract it from detailed probe if possible, or just ask user to enter it for now 
                 # as "Copy Source" is complex without data. 
                 # Actually, `probe_video` calls `ffprobe`. 
                 # Let's keep it simple: Ask user to enter value if they chose Custom.
                 # For "Source", maybe just print the source bitrate and ask them to type it?
                 # Or better, logic:
                 info = probe_video(ref_path)
                 if info.bitrate and info.bitrate.isdigit():
                     src_kbps = int(info.bitrate) // 1000
                     print_info(f"Kaynak Bitrate: ~{src_kbps}k")
                     video_bitrate = str(src_kbps) + "k"
                 else:
                     print_warning("Kaynak bitrate algilanamadi.")
                     video_bitrate = ask_text("Bitrate girin", "5M")
             except:
                 video_bitrate = ask_text("Bitrate girin", "5M")

    print_info(f"Ayarlar: {target_width}x{target_height} @ {target_fps} fps | {scale_algo} | Bitrate: {video_bitrate or 'Auto'}")

    return (
        codec_family,
        codec_config,
        target_width,
        target_height,
        target_fps,
        scale_algo,
        audio_bitrate,
        video_bitrate
    )


def check_video_compatibility(
    mode: str,
    intro_path: Optional[Path],
    loop_path: Optional[Path],
    single_video_path: Optional[Path],
    codec_config,
    target_width: int,
    target_height: int,
    target_fps: float,
) -> None:
    """Check video compatibility with target settings."""
    console.print()
    print_info("Video/Codec Analizi yapiliyor...")

    temp_runner = FFmpegRunner()
    temp_encoder = VideoEncoder(
        temp_runner, codec_config, width=target_width, height=target_height, fps=target_fps
    )

    if mode == "single":
        ok, reason = temp_encoder.check_compatibility(single_video_path)
        if ok:
            print_success(f"[CHECK] VIDEO: Uyumlu ({reason}) - Direct Copy yapilacak.")
        else:
            print_warning(f"[CHECK] VIDEO: Re-encode gerekli! -> {reason}")
    else:
        # Check INTRO
        ok_i, reason_i = temp_encoder.check_compatibility(intro_path)
        if ok_i:
            print_success(f"[CHECK] INTRO: Uyumlu ({reason_i})")
        else:
            print_warning(f"[CHECK] INTRO: Re-encode gerekli! -> {reason_i}")

        # Check LOOP
        ok_l, reason_l = temp_encoder.check_compatibility(loop_path)
        if ok_l:
            print_success(f"[CHECK] LOOP: Uyumlu ({reason_l})")
        else:
            print_warning(f"[CHECK] LOOP: Re-encode gerekli! -> {reason_l}")

    console.print()


def select_duration_and_audio(
    mode: str, single_video_path: Optional[Path], music_dir: Path
) -> Tuple:
    """
    Select video duration and audio tracks.

    Returns:
        Tuple of (total_seconds, dur_str, chosen_tracks, chosen_bgs)
    """
    # Duration
    console.print()
    if mode == "single" and single_video_path:
        total_seconds = int(get_duration(single_video_path))
        dur_str = format_duration(total_seconds)
        print_info(f"Tek video suresi kullanilacak: {dur_str}")
    else:
        total_seconds = ask_duration_components(default_hours=8)
        dur_str = format_duration(total_seconds)
        print_info(f"Hedef sure: {dur_str}")

    # Audio files
    tracks, backgrounds = list_audio_files(music_dir)

    if not tracks:
        print_error("music/ icinde track bulunamadi!")
        raise ValueError("No music tracks found")

    # Track selection
    console.print()
    print_audio_table(tracks, "Muzik Track'leri")

    track_mode = ask_choice(
        "Track secimi", ["Hepsi (listedeki sirayla)", "Belirli track'leri sec"], 1
    )

    if track_mode == 1:
        chosen_tracks = tracks
    else:
        indices = ask_multiple_choice("Track sec", [p.name for p in tracks])
        chosen_tracks = [tracks[i - 1] for i in indices]

    # Shuffle tracks for variety
    random.shuffle(chosen_tracks)
    print_info("Muzik listesi ve siralamasi karistirildi.")

    # Background selection
    chosen_bgs: List[Tuple[Path, float]] = []

    console.print()
    print_info("Background ses secenekleri:")

    bg_options = ["BG kullanma"]
    if backgrounds:
        bg_options.append(f"Mevcut BG dosyalarindan sec ({len(backgrounds)} adet)")
    bg_options.append("Track listesinden BG olarak kullan")

    bg_mode = ask_choice("Background secimi", bg_options, 1)

    if bg_mode == 1:
        # No BG
        pass

    elif bg_mode == 2 and backgrounds:
        # Select from existing BG files
        print_audio_table(backgrounds, "Background Sesler")

        select_mode = ask_choice("BG secimi", ["Hepsi", "Belirli BG'leri sec"], 1)

        if select_mode == 1:
            selected_bgs = backgrounds
        else:
            indices = ask_multiple_choice("BG sec", [p.name for p in backgrounds])
            selected_bgs = [backgrounds[i - 1] for i in indices]

        # Get dB for each
        console.print()
        print_info("Secilen BG'ler icin dB ayari (Enter = varsayilan):")
        for bg in selected_bgs:
            default_db = parse_background_gain_db(bg)
            db_str = ask_text(f"  {bg.name} dB", str(default_db))
            try:
                db = float(db_str)
            except ValueError:
                db = default_db
            chosen_bgs.append((bg, db))

    else:
        # Select track as BG
        console.print()
        print_info("Track listesinden BG olarak kullanilacak parca secin:")
        print_audio_table(tracks, "Muzik Track'leri (BG olarak)")

        available_for_bg = tracks

        indices = ask_multiple_choice(
            "BG olarak kullanilacak track(lar)", [p.name for p in available_for_bg], min_count=1
        )

        console.print()
        print_info("Secilen track'ler icin BG dB ayari:")
        for idx in indices:
            track = available_for_bg[idx - 1]
            db_str = ask_text(f"  {track.name} dB", "-8")
            try:
                db = float(db_str)
            except ValueError:
                db = -8.0
            chosen_bgs.append((track, db))

    return total_seconds, dur_str, chosen_tracks, chosen_bgs


def standardize_audio_files(
    chosen_tracks: List[Path],
    chosen_bgs: List[Tuple[Path, float]],
    music_dir: Path,
    run_log: Path,
    tmp_dir: Path,
) -> Tuple[List[Path], List[Tuple[Path, float]]]:
    """
    Standardize audio files to common format.

    Returns:
        Tuple of (new_tracks, new_bgs)
    """
    console.print()
    if not ask_confirm(
        "Muzik dosyalarini otomatik normalize edip arsivlemek ister misiniz?", default=True
    ):
        return chosen_tracks, chosen_bgs

    print_info("Muzik dosyalari standart (48kHz, 320k) formate donusturuluyor...")

    runner = FFmpegRunner(run_log)
    audio_processor = AudioProcessor(runner, tmp_dir)
    archive_dir = music_dir / "archive"

    def std_progress(name, current, total):
        console.print(f"  Processed {current}/{total}: {name}", end="\r")

    # Standardize Chosen Tracks
    to_std = [t for t in chosen_tracks]
    new_tracks = audio_processor.standardize_tracks(to_std, archive_dir, std_progress)

    # Update BGs if they are separate files
    bg_files = [b[0] for b in chosen_bgs if b[0] not in to_std]
    if bg_files:
        new_bgs = audio_processor.standardize_tracks(bg_files, archive_dir, std_progress)

        # Re-map chosen_bgs
        updated_bgs = []
        for b_path, b_db in chosen_bgs:
            if not b_path.exists() and b_path.with_suffix(".mp3").exists():
                updated_bgs.append((b_path.with_suffix(".mp3"), b_db))
            else:
                updated_bgs.append((b_path, b_db))
        chosen_bgs = updated_bgs

    print_success("Ses dosyalari standardize edildi.")
    return new_tracks, chosen_bgs


def configure_drive_upload() -> Tuple[bool, str]:
    """Configure Google Drive upload settings."""
    console.print()
    drive_enabled = False
    drive_folder_id = ""

    if ask_confirm("Render bitince videoyu Google Drive'a yedeklemek ister misiniz?", default=False):
        drive_enabled = True
        drive_folder_id = ask_text("Drive Klasor ID (Bos = Root)", "")

        try:
            from .drive import DriveUploader

            uploader = DriveUploader()
            if not uploader.authenticate():
                print_warning("Drive girisi yapilamadi! Tarayicida dogrulama gerekebilir.")
                print_info("Lutfen cikan linki takip edin veya credentials.json'i kontrol edin.")
        except ImportError:
            print_error("Drive modulu yuklenemedi!")
            drive_enabled = False

    return drive_enabled, drive_folder_id


def validate_audio_tracks(chosen_tracks: List[Path], run_log: Path, tmp_dir: Path) -> List[Path]:
    """Validate audio tracks and return valid ones."""
    console.print()
    print_info("Muzik dosyalari dogrulaniyor...")

    runner = FFmpegRunner(run_log)
    audio_processor = AudioProcessor(runner, tmp_dir)

    def validation_progress(name: str, current: int, total: int):
        console.print(f"  [{current}/{total}] {name}...", end="\r")

    valid_tracks, invalid_tracks = audio_processor.validate_tracks(
        chosen_tracks, validation_progress
    )
    console.print()

    if invalid_tracks:
        print_error(f"Bozuk muzik dosyalari tespit edildi ({len(invalid_tracks)} adet):")
        for track, error in invalid_tracks:
            console.print(f"  [error]✗[/] {track.name}: {error}")

        console.print()

        if valid_tracks:
            choice = ask_choice(
                "Ne yapmak istersiniz?",
                [
                    f"Sadece gecerli track'lerle devam et ({len(valid_tracks)} adet)",
                    "Iptal et ve muzikleri degistir",
                ],
                1,
            )

            if choice == 2:
                print_warning("Iptal edildi. Bozuk muzik dosyalarini degistirin.")
                raise ValueError("Invalid audio tracks")

            print_success(f"{len(valid_tracks)} gecerli track ile devam ediliyor.")
            return valid_tracks
        else:
            print_error("Hic gecerli track yok! Muzik dosyalarini kontrol edin.")
            raise ValueError("No valid audio tracks")
    else:
        print_success(f"Tum track'ler dogrulandi ({len(valid_tracks)} adet)")
        return valid_tracks


def render_pipeline(
    mode: str,
    intro_path: Optional[Path],
    loop_path: Optional[Path],
    single_video_path: Optional[Path],
    codec_config,
    target_width: int,
    target_height: int,
    target_fps: float,
    scale_algo: str,
    audio_bitrate: str,
    total_seconds: int,
    chosen_tracks: List[Path],
    chosen_bgs: List[Tuple[Path, float]],
    out_path: Path,
    run_log: Path,
    tmp_dir: Path,
    timed_effects: Optional[List[dict]] = None,
    keep_video_audio: bool = True,
    apply_audio_fades: bool = True,
    audio_fade_in_sec: float = 2.0,
    audio_fade_out_sec: float = 4.0,
    suppress_progress: bool = False,
    video_bitrate: Optional[str] = None,
) -> Tuple[Path, dict]:
    """
    Execute the render pipeline.

    Returns:
        Tuple of (final_output_path, step_times)
    """
    steps = ["Intro encode", "Loop encode", "Video concat", "Audio isleme", "Final mux"]

    step_times = {}
    render_start = time.perf_counter()

    console.print()

    # NVENC readiness check if hardware encoder is selected
    if "nvenc" in codec_config.encoder.lower():
        from config import check_nvenc_readiness
        nvenc_status = check_nvenc_readiness()
        if nvenc_status["ready"]:
            gpu_name = nvenc_status["gpu_name"]
            vram = nvenc_status["vram_total_mb"]
            print_success(f"NVENC hazir: {gpu_name} ({vram} MB VRAM)")
        else:
            print_warning("NVENC kullanılamıyor, software encoder'a geciliyor:")
            for issue in nvenc_status["issues"]:
                print_warning(f"  - {issue}")
            # Fallback to software encoder
            from config import get_best_encoder as _get_best_sw
            sw_family = codec_config.codec_family
            # Force software by clearing nvenc from available list
            from config import clear_encoder_cache
            clear_encoder_cache()
            # Get software fallback
            sw_codec_map = {"av1": "av1", "h264": "h264", "h265": "h265"}
            from .config import CODECS as _SW_CODECS
            sw_key = sw_codec_map.get(sw_family, "h264")
            if sw_key in _SW_CODECS:
                codec_config = _SW_CODECS[sw_key]
                print_info(f"Software encoder: {codec_config.name}")

    runner = FFmpegRunner(run_log)
    audio_processor = AudioProcessor(runner, tmp_dir)

    class DummyProgress:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def update(self, *args, **kwargs): pass
        def complete_step(self, *args, **kwargs): pass

    progress_ctx = MultiStepProgress(steps) if not suppress_progress else DummyProgress()
    
    with progress_ctx as progress:

        encoder = VideoEncoder(
            runner=runner,
            codec_config=codec_config,
            width=target_width,
            height=target_height,
            fps=target_fps,
        )

        intro_norm = tmp_dir / f"intro_norm_{codec_config.codec_family}.mp4"
        loop_norm = tmp_dir / f"loop_norm_{codec_config.codec_family}.mp4"
        video_only_single = tmp_dir / f"video_only_single_{codec_config.codec_family}.mp4"

        def make_progress_callback(step_idx: int):
            # Print step name, return None so FFmpeg shows raw terminal output
            step_name = steps[step_idx] if step_idx < len(steps) else "?"
            console.print(f"\n[bold cyan]▶ [{step_idx+1}/{len(steps)}] {step_name}[/bold cyan]")
            return None

        def apply_audio_extras(base_audio: Path) -> Path:
            audio_out = base_audio

            # Optional timed effects (ozel1)
            if timed_effects:
                effects_track = create_timed_effects_track(
                    runner,
                    tmp_dir,
                    timed_effects,
                    total_seconds,
                )
                if effects_track and effects_track.exists():
                    audio_out = audio_processor.mix_tracks(audio_out, [effects_track], total_seconds)

            return audio_out

        if mode == "single" and single_video_path:
            # Single video encode (no concat)
            t0 = time.perf_counter()
            video_only = encoder.normalize_video(
                single_video_path,
                video_only_single,
                make_progress_callback(0),
                scale_algo=scale_algo,
                bitrate=video_bitrate,
            )
            step_times["Intro encode"] = time.perf_counter() - t0
            progress.complete_step(0)
            step_times["Loop encode"] = 0
            progress.complete_step(1)
            step_times["Video concat"] = 0
            progress.complete_step(2)

            # Audio (sequential for single mode)
            t0 = time.perf_counter()
            music_loop = audio_processor.create_music_loop(
                chosen_tracks, total_seconds, pre_validated=True
            )

            if chosen_bgs:
                bg_processed = audio_processor.process_backgrounds(chosen_bgs)
                audio_full = audio_processor.mix_tracks(music_loop, bg_processed, total_seconds)
            else:
                audio_full = music_loop

            audio_full = apply_audio_extras(audio_full)

            step_times["Audio isleme"] = time.perf_counter() - t0
            progress.complete_step(3)
        else:
            # Parallel execution
            from concurrent.futures import ThreadPoolExecutor

            video_only = None
            audio_full = None

            def encode_video_branch():
                """Encode intro, loop, then concat."""
                nonlocal video_only

                # Encode intro
                t0 = time.perf_counter()
                encoder.normalize_video(
                    intro_path, intro_norm, make_progress_callback(0), scale_algo=scale_algo, bitrate=video_bitrate
                )
                intro_time = time.perf_counter() - t0
                progress.complete_step(0)

                # Encode loop
                t0 = time.perf_counter()
                encoder.normalize_video(
                    loop_path, loop_norm, make_progress_callback(1), scale_algo=scale_algo, bitrate=video_bitrate
                )
                loop_time = time.perf_counter() - t0
                progress.complete_step(1)

                # Concat
                t0 = time.perf_counter()
                video_only = encoder.concat_videos(
                    intro_norm, loop_norm, total_seconds, tmp_dir, make_progress_callback(2)
                )
                concat_time = time.perf_counter() - t0
                progress.complete_step(2)

                return intro_time, loop_time, concat_time

            def process_audio_branch():
                """Create music loop and mix with backgrounds."""
                nonlocal audio_full

                t0 = time.perf_counter()
                music_loop = audio_processor.create_music_loop(
                    chosen_tracks, total_seconds, pre_validated=True
                )

                if chosen_bgs:
                    bg_processed = audio_processor.process_backgrounds(chosen_bgs)
                    audio_full = audio_processor.mix_tracks(music_loop, bg_processed, total_seconds)
                else:
                    audio_full = music_loop

                audio_full = apply_audio_extras(audio_full)

                audio_time = time.perf_counter() - t0
                return audio_time

            # Run both branches in parallel
            with ThreadPoolExecutor(max_workers=2) as executor:
                video_future = executor.submit(encode_video_branch)
                audio_future = executor.submit(process_audio_branch)

                # Wait for both to complete
                intro_time, loop_time, concat_time = video_future.result()
                audio_time = audio_future.result()

            step_times["Intro encode"] = intro_time
            step_times["Loop encode"] = loop_time
            step_times["Video concat"] = concat_time
            step_times["Audio isleme"] = audio_time
            progress.complete_step(3)

        # Step 5: Final mux
        t0 = time.perf_counter()
        mux_video_audio(
            runner,
            video_only,
            audio_full,
            out_path,
            audio_bitrate=audio_bitrate,
            progress_callback=make_progress_callback(4),
            keep_video_audio=keep_video_audio,
            apply_audio_fades=apply_audio_fades,
            fade_in_sec=audio_fade_in_sec,
            fade_out_sec=audio_fade_out_sec,
        )
        step_times["Final mux"] = time.perf_counter() - t0
        progress.complete_step(4)

    # Post-render validation: Check if duration is correct
    print()
    print("[Render Sonrasi Kontrol]")
    try:
        from video_renderer.validator import PostRenderValidator
        
        validator = PostRenderValidator()
        result = validator.validate_output(
            out_path,
            target_duration=total_seconds,
            target_specs={
                "codec": "h264" if "h264" in codec_config.encoder.lower() else 
                         ("h265" if "hevc" in codec_config.encoder.lower() else "av1"),
                "width": target_width,
                "height": target_height,
                "fps": target_fps,
                "has_audio": True,
            }
        )
        
        if not result.valid and result.errors:
            # Check for duration errors specifically
            duration_errors = [e for e in result.errors if e.field == "duration"]
            if duration_errors:
                error = duration_errors[0]
                actual_duration = result.duration_seconds
                percent_diff = abs(actual_duration - total_seconds) / total_seconds * 100
                
                print(f"⚠ Duration Error: {error.message}")
                print(f"  Expected: {total_seconds}s, Got: {actual_duration:.1f}s ({percent_diff:.1f}% off)")
                print()
                
                # Offer emergency fix (frame-exact stream copy trim)
                fix_choice = ask_choice(
                    "Acil Durum Çözümü",
                    [
                        "1. Video'yu frame-exact trim et (hızlı, stream copy)",
                        "2. Olduğu gibi kalsın (skip)"
                    ],
                    default=1
                )
                
                if fix_choice == 1:
                    print()
                    print("[Emergency Fix: Frame-Exact Trim]")
                    if fix_video_duration(out_path, total_seconds, fps=target_fps):
                        print("  [OK] Video duration fixed!")
                    else:
                        print("  [ERROR] Fix failed, keeping original")
        else:
            # Duration OK
            print(f"  ✓ Duration: {result.duration_seconds:.1f}s (hedef {total_seconds}s)")
            print(f"  ✓ Codec: {result.video_info.get('codec', '?')}")
            print(f"  ✓ Resolution: {result.video_info.get('width')}x{result.video_info.get('height')}")
            print(f"  ✓ Audio: Mevcut" if result.video_info.get('has_audio') else "  ⚠ Audio: Yok")
    
    except Exception as e:
        print(f"  [WARN] Post-render validation skipped: {e}")

    # Calculate total render time
    render_total = time.perf_counter() - render_start

    # Format render time for filename
    render_mins = int(render_total // 60)
    render_secs = int(render_total % 60)
    time_suffix = f"_{render_mins}m{render_secs}s"

    # Rename output with time suffix
    new_out_name = out_path.stem + time_suffix + out_path.suffix
    new_out_path = out_path.parent / new_out_name
    try:
        out_path.rename(new_out_path)
        out_path = new_out_path
    except Exception:
        pass  # Keep original name if rename fails

    return out_path, step_times


def fix_video_duration(video_path: Path, target_seconds: int, fps: int = 60) -> bool:
    """
    Emergency post-render duration fix using frame-exact trim.
    
    Fixes videos where duration is wrong due to broken timestamps.
    Uses -vframes to bypass timestamp issues entirely.
    
    Strategy: Try stream copy first with -r + -fps_mode (MP4), then MKV fallback.
    
    This is FAST (stream copy, ~2-3 min for 8h video) and lossless.
    
    Args:
        video_path: Path to video file to fix
        target_seconds: Target duration in seconds
        fps: Frame rate (default 60)
    
    Returns:
        True if successful, False otherwise
    """
    import subprocess
    from pathlib import Path
    from video_renderer.ffmpeg import get_duration
    
    if not video_path.exists():
        print(f"  [ERROR] Video not found: {video_path}")
        return False
    
    target_frames = int(target_seconds * fps)
    tmp_fixed = video_path.parent / f"{video_path.stem}_fixed_tmp{video_path.suffix}"
    
    try:
        # Strategy 1: Stream copy with -r flag to reset FPS + -fps_mode CFR
        print(f"  [Stream Copy Fix] -r {fps} -fps_mode cfr -vframes {target_frames}")
        cmd = [
            "ffmpeg", "-y",
            "-r", str(fps),
            "-i", str(video_path),
            "-c:v", "copy", "-c:a", "copy",
            "-fps_mode", "cfr",
            "-vframes", str(target_frames),
            str(tmp_fixed),
        ]
        subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL, 
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Verify fixed video
        fixed_duration = get_duration(tmp_fixed)
        tolerance = max(2.0, target_seconds * 0.02)
        
        if fixed_duration > 10 and abs(fixed_duration - target_seconds) <= tolerance:
            print(f"  [OK] Stream copy fix succeeded: {fixed_duration:.1f}s")
            video_path.unlink()
            tmp_fixed.rename(video_path)
            print(f"  [OK] Fixed version saved")
            return True
        else:
            # Duration still wrong, try MKV fallback
            print(f"  [WARN] MP4 stream copy still wrong ({fixed_duration:.1f}s), trying MKV...")
            tmp_fixed.unlink()
            
            tmp_mkv = video_path.parent / f"{video_path.stem}_fixed_tmp.mkv"
            cmd_mkv = cmd.copy()
            cmd_mkv[cmd_mkv.index(str(tmp_fixed))] = str(tmp_mkv)
            
            try:
                subprocess.run(cmd_mkv, check=True, stdin=subprocess.DEVNULL,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                fixed_duration = get_duration(tmp_mkv)
                if fixed_duration > 10 and abs(fixed_duration - target_seconds) <= tolerance:
                    print(f"  [OK] MKV fix succeeded: {fixed_duration:.1f}s")
                    video_path.unlink()
                    new_mkv_path = video_path.parent / (video_path.stem + ".mkv")
                    tmp_mkv.rename(new_mkv_path)
                    print(f"  [OK] Fixed video saved as .mkv")
                    return True
                else:
                    print(f"  [ERROR] MKV format also failed ({fixed_duration:.1f}s)")
                    tmp_mkv.unlink()
                    return False
            except Exception as e:
                print(f"  [ERROR] MKV fallback failed: {e}")
                if tmp_mkv.exists():
                    tmp_mkv.unlink()
                return False
            
    except Exception as e:
        print(f"  [ERROR] Duration fix failed: {e}")
        if tmp_fixed.exists():
            tmp_fixed.unlink()
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# Render Pipeline (Main)
# ═══════════════════════════════════════════════════════════════════════════════
    """
    Run Batch Wizard (State Machine Implementation).
    Supports Back Navigation.
    """
    import shutil
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from rich.table import Table, box

    base = Path.cwd()
    music_dir = base / "music"
    tmp_dir = base / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    
    # Clean tmp
    for f in tmp_dir.glob("batch_job_*"):
        if f.is_dir(): shutil.rmtree(f, ignore_errors=True)
    
    state = {
        "base": base,
        "music_dir": music_dir,
        "tmp_dir": tmp_dir,
        "pairs": [],
        "settings_mode": 1, # 1=Native, 2=Uniform
        "global_config": None,
        "total_seconds": 0,
        "dur_str": "",
        "max_workers": 1,
        "jobs": [],
        "all_tracks": [],
        "all_bgs": [],
        "bg_strategy": 1,
        "fixed_bg": None
    }

    def step_init(s):
        print_header()
        print_info("Batch Modu Baslatiliyor...")
        if not check_ffmpeg_install(): return 2
        
        # Check music logic...
        all_tracks, all_bgs = list_audio_files(s["music_dir"])
        if not all_tracks:
            print_error("Music klasorunde track yok!")
            return 2
        s["all_tracks"] = all_tracks
        s["all_bgs"] = all_bgs

        # Smart Detect
        detector = SmartBatchDetector(s["base"])
        pairs = detector.scan()
        if not pairs:
            print_error("Hicbir uygun video cifti (intro+loop) bulunamadi.")
            return 2
        
        s["pairs"] = pairs
        
        # Display Pairs
        table = Table(title="Tespit Edilen Isler", box=box.ROUNDED)
        table.add_column("#", style="dim")
        table.add_column("Is Adi", style="bold yellow")
        table.add_column("Intro", style="cyan")
        table.add_column("Loop", style="blue")
        
        for i, p in enumerate(pairs, 1):
            table.add_row(str(i), p.name, p.intro.name, p.loop.name)
        console.print(table)
        
        if not ask_confirm("Bu isler dogru mu?", True): # Might enable Back here?
             return 1
        return 0

    def step_settings_mode(s):
        console.print()
        s["settings_mode"] = ask_choice(
            "Ayarlar Modu", 
            ["Otomatik / Native (Her video kendi codec/cozunurlugunu korur)", "Tek Tip (Tum videolari ayni formata cevir)"],
            1
        ) # Raises BN
        return 0

    def step_global_config(s):
        if s["settings_mode"] == 2:
            s["global_config"] = configure_render_settings("intro_loop", None, None, None) # Raises BN inside likely?
        else:
            s["global_config"] = None
        return 0

    def step_duration(s):
        console.print()
        s["total_seconds"] = ask_duration_components(default_hours=8) # Raises BN
        s["dur_str"] = format_duration(s["total_seconds"])
        return 0

    def step_concurrency(s):
        console.print()
        s["max_workers"] = ask_choice("Ayni anda kac video islensin?", ["1 (Sirali)", "2 (Es zamanli)", "3 (Es zamanli)"], 3) # Raises BN
        return 0

    def step_audio_strategy(s):
        # New Step: Define how audio is handled for all jobs
        console.print()
        print_info("Ses Ayarlari (Toplu)")
        
        # BG Strategy
        bg_strat = ask_choice("Arkaplan sesi (BG) nasil olsun?", 
            ["Rastgele (Her videoya farkli)", "Hicbirinde olmasin", "Hepsinde ayni (Sec...)"], 1) # BN
        
        s["bg_strategy"] = bg_strat
        if bg_strat == 3:
            # Select one BG
            print_audio_table(s["all_bgs"], "BG Listesi")
            idx = ask_int("BG Numarasi", 1, len(s["all_bgs"]), allow_back=True) # BN
            s["fixed_bg"] = s["all_bgs"][idx-1]
        
        return 0

    def step_generate_jobs(s):
        print_info("Isler hazirlaniyor...")
        s["jobs"] = []
        
        # Shuffle tracks once
        pool = list(s["all_tracks"])
        random.shuffle(pool)
        
        for i, pair in enumerate(s["pairs"], 1):
            # 1. Config (Native or Global)
            if s["settings_mode"] == 1:
                 # Native detection
                 try:
                    info = probe_video(pair.intro)
                    c_name = info.codec.lower()
                    if "av1" in c_name: c_fam = "av1"
                    elif "hevc" in c_name or "h265" in c_name: c_fam = "h265"
                    else: c_fam = "h264"
                    c_conf = get_best_encoder(c_fam)
                    t_w, t_h = info.width, info.height
                    try:
                        if "/" in info.fps: num,den=info.fps.split("/"); t_fps=float(num)/float(den)
                        else: t_fps=float(info.fps)
                    except: t_fps=30.0
                    j_conf = (c_fam, c_conf, t_w, t_h, t_fps, "lanczos", "192k")
                 except:
                    c_conf = get_best_encoder("h264")
                    j_conf = ("h264", c_conf, 1920, 1080, 30.0, "lanczos", "192k")
            else:
                 j_conf = s["global_config"]

            # 2. Tracks
            req_sec = s["total_seconds"]
            job_tracks = []
            current_dur = 0
            
            while current_dur < req_sec + 60:
                if not pool: 
                    pool = list(s["all_tracks"]); random.shuffle(pool)
                t = pool.pop(0)
                try: d = get_duration(t)
                except: d=180
                job_tracks.append(t)
                current_dur += d
            
            # 3. BG
            job_bgs = []
            strat = s.get("bg_strategy", 1)
            if strat == 2: pass # None
            elif strat == 3: # Fixed
                job_bgs.append((s["fixed_bg"], -15.0))
            else: # Random
                if s["all_bgs"]:
                     bg = random.choice(s["all_bgs"])
                     job_bgs.append((bg, -15.0))
            
            # Out path
            out_name = f"{pair.name}_render_{i}.mp4"
            out_path = s["base"] / "renders" / out_name
            
            s["jobs"].append({
                "id": i,
                "pair": pair,
                "config": j_conf,
                "tracks": job_tracks,
                "bgs": job_bgs,
                "out": out_path
            })
        
        console.print(f"\n[green]{len(s['jobs'])} adet is hazirlandi.[/]")
        return 0

    def step_confirm_start(s):
        c = ask_choice(f"{len(s['jobs'])} is baslatilsin mi?", ["Evet", "Hayir (Cikis)"], 1) # BN
        if c == 2: return 1
        return 0

    def step_execute_batch(s):
        # Run Threads
        print_info(f"Islem basliyor... (Concurrency: {s['max_workers']})")
        
        def process_job_wrapper(job):
            jid = job["id"]
            pair = job["pair"]
            (c_fam, c_conf, t_w, t_h, t_fps, s_algo, a_bit) = job["config"]
            
            job_tmp = s["tmp_dir"] / f"batch_job_{jid}"
            job_tmp.mkdir(exist_ok=True)
            job_log = job_tmp / "run.log"
            
            try:
                render_pipeline(
                    "intro_loop", pair.intro, pair.loop, None,
                    c_conf, t_w, t_h, t_fps, s_algo, a_bit,
                    s["total_seconds"], job["tracks"], job["bgs"], job["out"],
                    job_log, job_tmp, suppress_progress=True
                )
                print_success(f"[Job {jid}] Tamamlandi.")
            except Exception as e:
                print_error(f"Job {jid} failed: {e}")
                
        with ThreadPoolExecutor(max_workers=s["max_workers"]) as executor:
            futures = [executor.submit(process_job_wrapper, j) for j in s["jobs"]]
            for f in as_completed(futures):
                pass
                
        print_success("Batch tamamlandi.")
        return 0

    steps = [
        step_init,
        step_settings_mode,
        step_global_config, # skipped if native
        step_duration,
        step_concurrency,
        step_audio_strategy,
        step_generate_jobs,
        step_confirm_start,
        step_execute_batch
    ]
    
    curr = 0
    while 0 <= curr < len(steps):
        fn = steps[curr]
        try:
            res = fn(state)
            if res == 2: return 2
            if res == 1: return 0
            curr += 1
        except BackNavigation:
            if curr > 0:
                curr -= 1
                # Logic to skip backward over optional steps
                if curr == 2 and state["settings_mode"] == 1: 
                    curr = 1 # Skip global config backwards
            else:
                if ask_confirm("Cikilsin mi?", False): return 0

    return 0


def run_batch() -> int:
    return run_batch_wizard()


def handle_post_render_actions(
    out_path: Path,
    mode: str,
    intro_path: Optional[Path],
    loop_path: Optional[Path],
    single_video_path: Optional[Path],
    post_action: str,
    drive_enabled: bool,
    drive_folder_id: str,
    base: Path,
    step_times: dict,
) -> None:
    """Handle post-render actions (cleanup, archive, upload)."""
    # Completion with detailed timing
    final_duration = get_duration(out_path)

    console.print()
    console.print("=" * 60)
    console.print("[bold green]RENDER TAMAMLANDI[/]")
    console.print("=" * 60)
    console.print(f"[bold]Dosya:[/] {out_path.name}")
    console.print(
        f"[bold]Video Suresi:[/] {final_duration:.1f} saniye ({final_duration/3600:.2f} saat)"
    )
    console.print()
    console.print("[bold yellow]ADIM SURELERI:[/]")
    for step_name, step_time in step_times.items():
        if step_time > 0:
            mins = int(step_time // 60)
            secs = int(step_time % 60)
            console.print(f"  {step_name}: {mins}m {secs}s")
    console.print()

    # Calculate total render time
    render_total = sum(step_times.values())
    render_mins = int(render_total // 60)
    render_secs = int(render_total % 60)
    console.print(f"[bold cyan]TOPLAM RENDER:[/] {render_mins}m {render_secs}s")

    # Post action
    if post_action == "delete":
        try:
            if mode == "single" and single_video_path:
                single_video_path.unlink(missing_ok=True)
                print_success("Kaynak video silindi.")
            else:
                intro_path.unlink(missing_ok=True)
                loop_path.unlink(missing_ok=True)
                print_success("Kaynak intro/loop silindi.")
        except Exception as e:
            print_warning(f"Kaynak silme hatasi: {e}")

    elif post_action == "archive":
        archive_dir = base / "archive" / time.strftime("%Y%m%d_%H%M%S")
        archive_dir.mkdir(parents=True, exist_ok=True)
        try:
            if mode == "single" and single_video_path:
                single_video_path.rename(archive_dir / single_video_path.name)
                print_success(f"Kaynak video arsivlendi: {archive_dir.as_posix()}")
            else:
                intro_path.rename(archive_dir / intro_path.name)
                loop_path.rename(archive_dir / loop_path.name)
                print_success(f"Kaynak intro/loop arsivlendi: {archive_dir.as_posix()}")
        except Exception as e:
            print_warning(f"Arsivleme hatasi: {e}")

    # Drive Upload
    if drive_enabled:
        console.print()
        print_info("Google Drive'a yukleniyor...")

        try:
            from .drive import DriveUploader

            uploader = DriveUploader()
            success, file_id = uploader.upload_file(
                out_path, drive_folder_id if drive_folder_id else None
            )
            if success:
                print_success(f"Video basariyla yuklendi! ID: {file_id}")
            else:
                print_error(f"Yukleme basarisiz: {file_id}")
        except Exception as e:
            print_error(f"Upload hatasi: {e}")


def run_interactive(ozel1_mode: bool = False) -> int:
    """
    Run the interactive render wizard (State Machine Implementation).
    Supports Back Navigation.
    """
    base = Path.cwd()
    music_dir = base / "music"
    run_id, tmp_dir = create_run_tmp_dir(base)

    run_log = tmp_dir / "run_log.txt"
    err_log = tmp_dir / "error_log.txt"
    session_json = base / "tmp" / "last_session.json"
    
    # State Data
    state = {
        "base": base,
        "music_dir": music_dir,
        "tmp_dir": tmp_dir,
        "run_id": run_id,
        "run_log": run_log,
        "videos": [],
        "mode": "standard",
        "intro_path": None,
        "loop_path": None,
        "single_video_path": None,
        # Config
        "codec_family": "h264",
        "codec_config": None,
        "target_width": 1920,
        "target_height": 1080,
        "target_fps": 60.0,
        "scale_algo": "lanczos",
        "audio_bitrate": "192k",
        "video_bitrate": None,
        # Duration/Audio
        "total_seconds": 0,
        "dur_str": "",
        "chosen_tracks": [],
        "chosen_bgs": [],
        "timed_effects": [],
        "video_audio_mode": "keep",
        "apply_audio_fades": True,
        "audio_fade_in_sec": 2.0,
        "audio_fade_out_sec": 4.0,
        "ozel1_mode": ozel1_mode,
        # Drive/Post
        "drive_enabled": False,
        "drive_folder_id": "",
        "out_path": None,
        "post_action": "keep",
    }

    # Step Functions
    def step_check_env(s):
        print_header()
        print_working_directory(s["base"])
        if not check_ffmpeg_install(): return 2
        
        # Check music dir
        music_candidates = [s["base"] / "music", s["base"] / "Music"]
        found = False
        for c in music_candidates:
            if c.exists() and c.is_dir():
                s["music_dir"] = c
                found = True
                break
        if not found:
            print_error(f"'{s['music_dir'].name}/' klasoru bulunamadi!")
            return 2
            
        # List videos
        videos = list_video_files(s["base"])
        if not videos:
            print_error("Video bulunamadi!")
            return 2
        s["videos"] = videos
        print_video_table(videos)
        return 0

    def step_select_mode(s):
        try:
            s["mode"] = select_render_mode(s["videos"]) # Has no back logic inside, modify if need
        except BackNavigation:
            raise # Propagate
        return 0

    def step_select_videos(s):
        i, l, sv = select_videos_for_mode(s["mode"], s["videos"])
        s["intro_path"] = i
        s["loop_path"] = l
        s["single_video_path"] = sv
        return 0

    def step_config(s):
        (cf, cc, tw, th, tf, sa, ab, vb) = configure_render_settings(
            s["mode"], s["intro_path"], s["loop_path"], s["single_video_path"]
        )
        s["codec_family"] = cf
        s["codec_config"] = cc
        s["target_width"] = tw
        s["target_height"] = th
        s["target_fps"] = tf
        s["scale_algo"] = sa
        s["audio_bitrate"] = ab
        s["video_bitrate"] = vb
        return 0

    def step_check_compat(s):
        check_video_compatibility(
            s["mode"], s["intro_path"], s["loop_path"], s["single_video_path"],
            s["codec_config"], s["target_width"], s["target_height"], s["target_fps"]
        )
        # Just confirmation/info, auto proceed usually
        return 0

    def step_duration_audio(s):
        # Duration
        console.print()
        if s["mode"] == "single" and s["single_video_path"]:
            total = int(get_duration(s["single_video_path"]))
            dur_str = format_duration(total)
            print_info(f"Tek video suresi kullanilacak: {dur_str}")
        else:
            total = ask_duration_components(default_hours=8) # Raises BN
            dur_str = format_duration(total)
        
        s["total_seconds"] = total
        s["dur_str"] = dur_str

        # Audio
        all_tracks, all_bgs = list_audio_files(s["music_dir"])
        if not all_tracks: raise ValueError("No music")
        
        console.print()
        print_audio_table(all_tracks, "Muzik Track'leri")
        
        # Track Selection
        tm = ask_choice("Track secimi", ["Hepsi", "Belirli track'ler"], 1) # Raises BN
        if tm == 1:
            chosen = all_tracks
        else:
            indices = ask_multiple_choice("Track sec", [p.name for p in all_tracks]) # Raises BN
            chosen = [all_tracks[i-1] for i in indices]
        
        random.shuffle(chosen)
        s["chosen_tracks"] = chosen
        
        # BG Selection
        chosen_bgs = []
        bg_opts = ["BG kullanma"] + ([f"Mevcut BG ({len(all_bgs)})"] if all_bgs else []) + ["Track listesinden"]
        bg_mode = ask_choice("Background secimi", bg_opts, 1) # Raises BN
        
        if bg_mode == 1: pass
        elif bg_mode == 2 and all_bgs:
            # Existing BGs
            print_audio_table(all_bgs, "BG Sesler")
            sm = ask_choice("BG secimi", ["Hepsi", "Belirli BG'ler"], 1) # Raises BN
            if sm == 1: sels = all_bgs
            else:
                idxs = ask_multiple_choice("BG sec", [p.name for p in all_bgs]) # Raises BN
                sels = [all_bgs[i-1] for i in idxs]
            
            for bg in sels:
                def_db = parse_background_gain_db(bg)
                db_s = ask_text(f"  {bg.name} dB", str(def_db)) # Raises BN
                try: db = float(db_s)
                except: db = def_db
                chosen_bgs.append((bg, db))
                
        else:
            # Track as BG
            print_audio_table(all_tracks, "Trackler (BG)")
            idxs = ask_multiple_choice("BG olacak trackler", [p.name for p in all_tracks], min_count=1) # Raises BN
            for idx in idxs:
                tr = all_tracks[idx-1]
                db_s = ask_text(f"  {tr.name} dB", "-8") # Raises BN
                try: db = float(db_s)
                except: db = -8.0
                chosen_bgs.append((tr, db))
                
        s["chosen_bgs"] = chosen_bgs

        # Intro/Loop video sesi: varsayilan "degistirme" (koru)
        console.print()
        va_choice = ask_choice(
            "Intro/Loop video sesi",
            ["Degistirme (sesi koru)", "Kaldir (videoyu sessiz kullan)"],
            1,
        )
        s["video_audio_mode"] = "keep" if va_choice == 1 else "remove"

        # Müzik/ses fade in/out
        s["apply_audio_fades"] = ask_confirm(
            "Muzik/seslerde baslangicta fade-in ve sonda fade-out uygulansin mi?",
            True,
        )
        if s["apply_audio_fades"]:
            fi_str = ask_text("Fade-in suresi (sn)", "2.0")
            fo_str = ask_text("Fade-out suresi (sn)", "4.0")
            try:
                s["audio_fade_in_sec"] = max(0.0, float(fi_str))
            except Exception:
                s["audio_fade_in_sec"] = 2.0
            try:
                s["audio_fade_out_sec"] = max(0.0, float(fo_str))
            except Exception:
                s["audio_fade_out_sec"] = 4.0

        # Ozel1: zamanli tek-sefer efektler
        if s.get("ozel1_mode"):
            s["timed_effects"] = []
            if ask_confirm("OZEL1 aktif: Zamanli efekt sesleri eklensin mi?", True):
                effect_pool = sorted({*all_tracks, *all_bgs}, key=lambda p: p.name.lower())
                if effect_pool:
                    print_audio_table(effect_pool, "OZEL1 Efekt Havuzu")
                    selected = ask_multiple_choice(
                        "Efekt sesi/secimleri",
                        [p.name for p in effect_pool],
                        min_count=1,
                    )
                    for idx in selected:
                        sfx = effect_pool[idx - 1]
                        start_after = ask_int(f"{sfx.name} ilk calma (sn)", 0, 86400)
                        interval_sec = ask_int(f"{sfx.name} tekrar araligi (sn)", 1, 86400, 20)
                        max_plays = ask_int(
                            f"{sfx.name} maksimum tekrar (0=sinirsiz)",
                            0,
                            10000,
                            0,
                        )
                        gain_text = ask_text(f"{sfx.name} ses seviyesi dB", "-6")
                        fade_in_text = ask_text(f"{sfx.name} fade-in (sn)", "0.1")
                        fade_out_text = ask_text(f"{sfx.name} fade-out (sn)", "0.5")

                        try:
                            gain_db = float(gain_text)
                        except Exception:
                            gain_db = -6.0
                        try:
                            fade_in = max(0.0, float(fade_in_text))
                        except Exception:
                            fade_in = 0.1
                        try:
                            fade_out = max(0.0, float(fade_out_text))
                        except Exception:
                            fade_out = 0.5

                        s["timed_effects"].append(
                            {
                                "path": sfx.as_posix(),
                                "start_after_sec": start_after,
                                "interval_sec": interval_sec,
                                "max_plays": max_plays,
                                "gain_db": gain_db,
                                "fade_in_sec": fade_in,
                                "fade_out_sec": fade_out,
                            }
                        )
        return 0

    def step_std_audio(s):
        # Allow back before expensive operation? 
        # Actually this step modifies files. 
        # If user goes back after this, files are already changed.
        # But we can ask confirmation or just do it.
        # Let's skip user interaction for standardization here or make it skippable
        s["chosen_tracks"], s["chosen_bgs"] = standardize_audio_files(
            s["chosen_tracks"], s["chosen_bgs"], s["music_dir"], s["run_log"], s["tmp_dir"]
        )
        return 0

    def step_drive(s):
        en, fid = configure_drive_upload() # Raises BN
        s["drive_enabled"] = en
        s["drive_folder_id"] = fid
        return 0

    def step_post(s):
        # Output filename
        s["out_path"] = get_output_filename(s["mode"], s["single_video_path"], s["codec_family"], s["dur_str"])
        
        console.print()
        idx = ask_choice("Is bittikten sonra kaynak?", ["Kalsin", "Arsivle", "Sil"], 1) # Raises BN
        s["post_action"] = ["keep", "archive", "delete"][idx-1]
        return 0

    def step_summary(s):
        print_summary(
            s["intro_path"], s["loop_path"], s["codec_family"], s["dur_str"],
            s["chosen_tracks"], s["chosen_bgs"], s["out_path"], s["post_action"], s["single_video_path"]
        )
        if not ask_confirm("Devam edilsin mi?", True): # Raises BN (b=no or back?)
            # ask_confirm doesn't natively support BackNavigation in tui.py yet?
            # It uses Confirm.ask which returns bool.
            # We need to wrap it or handle it. 
            # Logic: No -> Back? Or No -> Cancel?
            # Usually No -> Cancel. 
            # But let's assume 'b' is not supported in Confirm.ask natively by Rich.
            # We can use ask_choice("Devam?", ["Evet", "Hayir", "Geri"])
            pass 
        return 0

    def step_execute(s):
        # Verification
        s["chosen_tracks"] = validate_audio_tracks(s["chosen_tracks"], s["run_log"], s["tmp_dir"])
        
        # Save Session
        sess = {
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "run_id": s["run_id"],
            "tmp_dir": s["tmp_dir"].as_posix(),
            "mode": s["mode"],
            "intro": s["intro_path"].as_posix() if s["intro_path"] else None,
            "loop": s["loop_path"].as_posix() if s["loop_path"] else None,
            "video": s["single_video_path"].as_posix() if s["single_video_path"] else None,
            "codec": s["codec_family"],
            "encoder": s["codec_config"].encoder if s["codec_config"] else "",
            "duration": s["dur_str"],
            "duration_sec": s["total_seconds"],
            "tracks": [p.as_posix() for p in s["chosen_tracks"]],
            "tracks_validated": True,
            "bgs": [{"path": p.as_posix(), "db": db} for p, db in s["chosen_bgs"]],
            "timed_effects": s.get("timed_effects", []),
            "out": s["out_path"].as_posix(),
            "post_action": s["post_action"],
            "config": {
                "width": s["target_width"],
                "height": s["target_height"],
                "fps": s["target_fps"],
                "scale_algo": s["scale_algo"],
                "audio_bitrate": s["audio_bitrate"],
                "video_audio_mode": s.get("video_audio_mode", "keep"),
                "apply_audio_fades": s.get("apply_audio_fades", True),
                "audio_fade_in_sec": s.get("audio_fade_in_sec", 2.0),
                "audio_fade_out_sec": s.get("audio_fade_out_sec", 4.0),
                "drive_enabled": s["drive_enabled"],
                "drive_folder_id": s["drive_folder_id"],
            },
        }
        session_json.write_text(json.dumps(sess))
        
        # Render
        s["out_path"], times = render_pipeline(
            s["mode"], s["intro_path"], s["loop_path"], s["single_video_path"],
            s["codec_config"], s["target_width"], s["target_height"], s["target_fps"],
            s["scale_algo"], s["audio_bitrate"], s["total_seconds"],
            s["chosen_tracks"], s["chosen_bgs"], s["out_path"],
            s["run_log"], s["tmp_dir"],
            timed_effects=s.get("timed_effects", []),
            keep_video_audio=(s.get("video_audio_mode", "keep") == "keep"),
            apply_audio_fades=s.get("apply_audio_fades", True),
            audio_fade_in_sec=s.get("audio_fade_in_sec", 2.0),
            audio_fade_out_sec=s.get("audio_fade_out_sec", 4.0),
            video_bitrate=s.get("video_bitrate"),
        )

        run_post_render_review_cli(
            s["out_path"],
            s["total_seconds"],
            {
                "codec": s["codec_family"],
                "width": s["target_width"],
                "height": s["target_height"],
                "fps": s["target_fps"],
                "has_audio": True,
            },
        )
        
        # Post Actions
        handle_post_render_actions(
            s["out_path"], s["mode"], s["intro_path"], s["loop_path"], s["single_video_path"],
            s["post_action"], s["drive_enabled"], s["drive_folder_id"], s["base"], times
        )
        return 0

    # Step Check logic to handle Confirm separately
    def step_final_confirm(s):
        # We replace standard Confirm with a Choice to allow Back
        c = ask_choice("Baslatilsin mi?", ["Evet", "Hayir (Cikis)"], 1) # Raises BN
        if c == 2: return 1 # Exit
        return 0

    steps = [
        step_check_env,     # 0
        step_select_mode,   # 1
        step_select_videos, # 2
        step_config,        # 3
        step_check_compat,  # 4
        step_duration_audio,# 5
        step_std_audio,     # 6
        step_drive,         # 7
        step_post,          # 8
        step_summary,       # 9
        step_final_confirm, # 10
        step_execute        # 11
    ]

    curr = 0
    try:
        while 0 <= curr < len(steps):
            fn = steps[curr]
            try:
                res = fn(state)
                if res == 2: return 2 # Critical Error
                if res == 1: return 0 # User Exit
                curr += 1
            except BackNavigation:
                if curr > 0:
                    curr -= 1
                    # Skip some steps backwards? 
                    # e.g. going back from duration(5) -> compat(4) -> config(3).
                    # Compat(4) is auto info, so we might want to skip it backwards to 3?
                    if curr == 6: curr = 5 # Back from std_audio -> duration?
                    if curr == 4: curr = 3 # Back from Compat -> Config
                else:
                    if ask_confirm("Sihirbazdan cikilsin mi?", default=False):
                        return 0
        return 0


    except KeyboardInterrupt:
        console.print()
        print_warning("Kullanici tarafindan iptal edildi.")
        return 130

    except Exception as e:
        tb = traceback.format_exc()
        msg = f"# ERROR — {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n{tb}\n"
        err_log.write_text(msg, encoding="utf-8")

        console.print()
        print_error(f"Hata olustu: {e}")
        print_info(f"Detaylar: {err_log.as_posix()}")
        return 4


# ═══════════════════════════════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════════════════════════════


def main() -> int:
    """Main entry point with interactive loop."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Video Renderer - Intro+Loop video birlestirme ve ses miksaji",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ornekler:
  python -m video_renderer              # Interaktif mod
  python -m video_renderer --version    # Versiyon goster
  python -m video_renderer --list-hw    # HW encoder'lari listele
  python -m video_renderer --resume     # Kaldigi yerden devam et
  python -m video_renderer --tui        # TUI arayuzunu baslat
  python -m video_renderer --tui --rm   # TUI + RAM-optimizasyon modu
        """,
    )

    parser.add_argument(
        "--version", "-v", action="version", version=f"Video Renderer {__version__}"
    )

    parser.add_argument(
        "--list-hw", action="store_true", help="Kullanilabilir hardware encoder'lari listele"
    )

    parser.add_argument(
        "--resume", "-r", action="store_true", help="Son session'dan kaldigi yerden devam et"
    )

    parser.add_argument(
        "--no-loop", action="store_true", help="Hata durumunda donguye girmeden cik"
    )

    parser.add_argument("--tui", action="store_true", help="Yeni Textual TUI arayuzunu kullan")

    parser.add_argument(
        "--ozel1",
        action="store_true",
        help="Ozel1 modu - zamanli tek-sefer efekt sesleri ve gelismis ses kontrolu",
    )

    parser.add_argument(
        "--batch",
        action="store_true",
        help="Smart Batch modu - Otomatik intro/loop ciftlerini tespit et ve sirali render yap",
    )

    # Unified render mode selection
    parser.add_argument(
        "--mode",
        choices=["standard", "ramtest", "ramdisk", "high_vram"],
        default="standard",
        help="Render mode (standard, ramtest, ramdisk, high_vram)",
    )

    # Unified render mode flags (aliases for --mode)
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--rm",
        "--ramtest",
        action="store_true",
        dest="ramtest",
        help="RAM-optimizasyon modu (Ramtest) - tmpfs ve yüksek VRAM optimize",
    )
    mode_group.add_argument(
        "--ramdisk", action="store_true", help="RAM Disk modu - Sadece RAM disk kullanimi"
    )
    mode_group.add_argument(
        "--high-vram", action="store_true", help="High VRAM modu - Yüksek GPU bellek optimizasyonu"
    )

    args = parser.parse_args()

    # Determine unified mode (--mode takes priority over legacy flags)
    mode: str = args.mode
    mode_info = ""

    # Legacy flag support (--rm, --ramdisk, --high-vram override --mode)
    if args.ramtest:
        mode = "ramtest"
        mode_info = "[RAMTEST] RAM-optimizasyon modu aktif"
    elif args.ramdisk:
        mode = "ramdisk"
        mode_info = "[RAMDISK] RAM disk modu aktif"
    elif args.high_vram:
        mode = "high_vram"
        mode_info = "[HIGHVRAM] Yüksek VRAM modu aktif"
    elif mode != "standard":
        mode_info = f"[{mode.upper()}] {mode} modu aktif"

    # Print mode info
    if mode != "standard":
        print(mode_info)
        from config import RamTestConfig, get_ramdisk_path

        ramtest_cfg = RamTestConfig(enabled=True, use_ramdisk=(mode in ["ramtest", "ramdisk"]))
        print(f"  - RAM Disk: {ramtest_cfg.use_ramdisk}")
        print(f"  - High VRAM: {ramtest_cfg.high_vram}")
        if ramtest_cfg.use_ramdisk:
            ramdisk = get_ramdisk_path()
            if ramdisk:
                print(f"  - RAM Disk Path: {ramdisk}")
            else:
                print(f"  - RAM Disk: Not available (using disk tmp)")

    # List hardware encoders
    if args.list_hw:
        print_header()
        console.print("[header]Hardware Encoders:[/]\n")

        encoders = detect_available_encoders()
        for name, available in encoders.items():
            status = "[success]✓ Mevcut[/]" if available else "[muted]✗ Yok[/]"
            console.print(f"  {name}: {status}")

        return 0

    # Launch Textual TUI if requested
    if args.tui:
        from .app import run_tui

        return run_tui(mode=mode)

    # Smart Batch mode
    if args.batch:
        return run_batch()

    # Direct resume mode
    if args.resume:
        result = run_resume()
        if result == 0 or args.no_loop:
            return result
        # Fall through to main loop on error

    # Main application loop
    base = Path.cwd()
    tmp_dir = base / "tmp"
    session_json = tmp_dir / "last_session.json"

    while True:
        try:
            print_header()

            # Check for existing session on startup
            if session_json.exists():
                try:
                    session = json.loads(session_json.read_text(encoding="utf-8"))
                    console.print()
                    print_info(f"Onceki session bulundu: {session.get('ts', 'unknown')}")
                    print_info(f"Hedef: {Path(session.get('out', '')).name}")

                    choice = ask_choice(
                        "Ne yapmak istersiniz?",
                        ["Kaldigi yerden devam et", "Yeni render baslat", "Cikis"],
                        1,
                    )

                    if choice == 1:
                        result = run_resume()
                        if result == 0:
                            # Success - ask what to do next
                            console.print()
                            next_choice = ask_choice(
                                "Render tamamlandi! Ne yapmak istersiniz?",
                                ["Yeni render baslat", "Cikis"],
                                1,
                            )
                            if next_choice == 2:
                                # Success cleanup
                                session_json.unlink(missing_ok=True)
                                return 0
                            # cleanup for new render
                            session_json.unlink(missing_ok=True)
                            continue  # Start new render
                        else:
                            # Error occurred - will be handled below
                            raise Exception("Resume sirasinda hata olustu")

                    elif choice == 2:
                        # Delete old session and start fresh
                        session_json.unlink(missing_ok=True)
                        # Clean tmp files for fresh start
                        for f in tmp_dir.glob("*.mp4"):
                            f.unlink(missing_ok=True)
                        for f in tmp_dir.glob("*.w64"):
                            f.unlink(missing_ok=True)

                    elif choice == 3:
                        return 0

                except json.JSONDecodeError:
                    session_json.unlink(missing_ok=True)

            # Run interactive wizard
            result = run_interactive(ozel1_mode=args.ozel1)

            if result == 0:
                # Success
                console.print()
                next_choice = ask_choice(
                    "Render tamamlandi! Ne yapmak istersiniz?", ["Yeni render baslat", "Cikis"], 1
                )
                if next_choice == 2:
                    session_json.unlink(missing_ok=True)
                    return 0
                session_json.unlink(missing_ok=True)
                continue

            elif result == 130:
                # Ctrl+C
                return 130

            else:
                # Error occurred
                raise Exception(f"Render hatasi (kod: {result})")

        except KeyboardInterrupt:
            console.print()
            print_warning("Kullanici tarafindan iptal edildi.")
            return 130

        except Exception as e:
            console.print()
            print_error(f"Hata: {e}")

            if args.no_loop:
                return 4

            # Offer options instead of exiting
            console.print()
            choice = ask_choice(
                "Ne yapmak istersiniz?",
                ["Kaldigi yerden devam et (--resume)", "Yeni render baslat", "Cikis"],
                1,
            )

            if choice == 1:
                continue  # Will check for session and resume
            elif choice == 2:
                # Clean session for fresh start
                session_json.unlink(missing_ok=True)
                continue
            else:
                return 4


if __name__ == "__main__":
    raise SystemExit(main())
