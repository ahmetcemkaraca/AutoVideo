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
from pathlib import Path
from typing import List, Tuple, Optional

from . import __version__
from .config import (
    RenderConfig, VIDEO_EXTENSIONS, AUDIO_EXTENSIONS,
    get_best_encoder, detect_available_encoders, CODECS
)
from .ffmpeg import FFmpegRunner, probe_video, get_duration, VideoInfo
from .video import VideoEncoder, encode_parallel
from .audio import (
    AudioProcessor, is_background_file, parse_background_gain_db,
    mux_video_audio
)
from .tui import (
    console, print_header, print_working_directory,
    print_video_table, print_audio_table, print_video_info_panel,
    ask_text, ask_int, ask_choice, ask_confirm, ask_multiple_choice,
    print_summary, print_completion, print_success, print_error,
    print_warning, print_info, MultiStepProgress, ask_duration_components
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
        except Exception as e:
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


# ═══════════════════════════════════════════════════════════════════════════════
# Resume Support
# ═══════════════════════════════════════════════════════════════════════════════

def run_resume() -> int:
    """Resume from last session."""
    base = Path.cwd()
    tmp_dir = base / "tmp"
    session_json = tmp_dir / "last_session.json"
    run_log = tmp_dir / "run_log.txt"
    err_log = tmp_dir / "error_log.txt"
    
    print_header()
    print_working_directory(base)
    
    if not session_json.exists():
        print_error("Devam edilecek session bulunamadi!")
        print_info("Once normal render baslatin, sonra --resume kullanin.")
        return 2
    
    try:
        session = json.loads(session_json.read_text(encoding="utf-8"))
    except Exception as e:
        print_error(f"Session dosyasi okunamadi: {e}")
        return 2
    
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
    
    print_success(f"Session bulundu: {session['ts']}")
    print_info(f"Hedef: {out_path.name} ({dur_str})")
    print_info(f"Ayarlar: {target_width}x{target_height} @ {target_fps} fps | {scale_algo} | {audio_bitrate}")
    
    # Define output paths for each step
    intro_norm = tmp_dir / f"intro_norm_{codec_family}.mp4"
    loop_norm = tmp_dir / f"loop_norm_{codec_family}.mp4"
    video_only_single = tmp_dir / f"video_only_single_{codec_family}.mp4"
    video_only_pattern = tmp_dir / "video_only_*.mp4"
    music_loop = tmp_dir / "music_loop.w64"
    audio_mixed = tmp_dir / "audio_mixed.w64"
    
    try:
        runner = FFmpegRunner(run_log)
        
        steps = [
            "Intro encode",
            "Loop encode",
            "Video concat",
            "Audio isleme",
            "Final mux"
        ]
        
        console.print()
        
        with MultiStepProgress(steps) as progress:
            
            encoder = VideoEncoder(
                runner=runner,
                codec_config=codec_config,
                width=target_width,
                height=target_height,
                fps=target_fps
            )
            
            def make_progress_callback(step_idx: int):
                def callback(p):
                    progress.update(step_idx, p.percent)
                return callback
            
            # Step 1-3: Video processing
            if mode == "single" and single_video_path:
                if total_seconds <= 0:
                    total_seconds = int(get_duration(single_video_path))
                if video_only_single.exists():
                    video_only = video_only_single
                    print_info("Tek video encode zaten var, atlaniyor...")
                else:
                    video_only = encoder.normalize_video(
                        single_video_path, video_only_single, 
                        make_progress_callback(0),
                        scale_algo=scale_algo
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
                        intro_path, intro_norm, 
                        make_progress_callback(0), 
                        scale_algo=scale_algo
                    )
                    progress.complete_step(0)
                
                # Step 2: Encode loop (skip if exists)
                if loop_norm.exists():
                    print_info(f"Loop zaten encode edilmis, atlaniyor...")
                    progress.complete_step(1)
                else:
                    encoder.normalize_video(
                        loop_path, loop_norm, 
                        make_progress_callback(1),
                        scale_algo=scale_algo
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
                        intro_norm, loop_norm,
                        total_seconds, tmp_dir,
                        make_progress_callback(2)
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
                
                progress.complete_step(3)
            
            # Step 5: Final mux (always run if output doesn't exist)
            if out_path.exists():
                print_info(f"Final dosya zaten var, atlaniyor...")
                progress.complete_step(4)
            else:
                mux_video_audio(
                    runner, video_only, audio_full, out_path,
                    audio_bitrate=audio_bitrate,
                    progress_callback=make_progress_callback(4)
                )
                progress.complete_step(4)
        
        # Completion
        final_duration = get_duration(out_path)
        print_completion(out_path, final_duration)
        
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
                success, file_id = uploader.upload_file(out_path, drive_folder_id if drive_folder_id else None)
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
# Interactive Wizard
# ═══════════════════════════════════════════════════════════════════════════════

def run_interactive() -> int:
    """Run the interactive render wizard."""
    base = Path.cwd()
    music_dir = base / "music"
    tmp_dir = base / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    
    run_log = tmp_dir / "run_log.txt"
    err_log = tmp_dir / "error_log.txt"
    session_json = tmp_dir / "last_session.json"
    
    try:
        # Header
        print_header()
        print_working_directory(base)
        
        # Check FFmpeg
        if not check_ffmpeg_install():
            return 2
        
        # Check music dir (case insensitive)
        music_candidates = [base / "music", base / "Music"]
        found_music = False
        for candidate in music_candidates:
            if candidate.exists() and candidate.is_dir():
                music_dir = candidate
                found_music = True
                break
        
        if not found_music:
            print_error(f"'{music_dir.name}/' klasoru bulunamadi!")
            print_info(f"Beklenen konum: {music_dir.resolve()}")
            print_info("Lutfen 'music' klasoru olusturun ve ses dosyalarini icine atin.")
            return 2
        
        # List videos
        videos = list_video_files(base)
        if len(videos) < 1:
            print_error("Video bulunamadi!")
            print_info(f"Lutfen su konuma video (mp4/mkv) dosyalarini atin:\n{base.resolve()}")
            return 2
        
        print_video_table(videos)
        
        # Select render mode
        mode_idx = ask_choice("Render modu", ["Intro + Loop", "Tek Video (sesi degistir)"], 1)
        mode = "intro_loop" if mode_idx == 1 else "single"

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
                return 2
            
            intro_path, intro_info = videos[intro_idx - 1]
            loop_path, loop_info = videos[loop_idx - 1]
            
            # Show detailed info
            print_video_info_panel("INTRO", intro_path, intro_info)
            print_video_info_panel("LOOP", loop_path, loop_info)
        
        # ──────────────────────────────────────────────────────────────
        # Configuration Mode
        # ──────────────────────────────────────────────────────────────
        console.print()
        config_mode_idx = ask_choice("Ayarlar Modu", [
            "[green]Basit[/] (Otomatik 1080p @ 60fps, Standart Kalite)",
            "[blue]Orta[/] (Cozunurluk Secimi, Otomatik Upscale)",
            "[yellow]Gelismis[/] (Cozunurluk, FPS, Upscale Metodu, Preset)",
            "[red]Ozel[/] (Her seyi elle ayarla)"
        ], 1)
        
        # Default Settings
        target_width = 1920
        target_height = 1080
        target_fps = 60
        scale_algo = "lanczos"
        audio_bitrate = "192k"
        
        available_encoders = detect_available_encoders()
        hw_available = any(available_encoders.values())
        
        if config_mode_idx == 1: # Basit
            # Force Defaults: 1080p, 60fps, AV1, Lanczos
            print_info("Basit Mod: Otomatik analiz yapiliyor...")
            
            # Check source resolution to avoid unnecessary re-encode/resize
            smart_res_found = False
            
            if mode == "single" and single_video_path:
                try:
                    ref_info = probe_video(single_video_path)
                    target_width, target_height = ref_info.width, ref_info.height
                    target_fps = float(ref_info.fps.split('/')[0]) / float(ref_info.fps.split('/')[1]) if '/' in ref_info.fps else float(ref_info.fps)
                    smart_res_found = True
                    print_success(f"Kaynak cozunurlugu kullanilacak: {target_width}x{target_height} @ {target_fps:.2f}fps")
                except Exception as e:
                    print_warning(f"Video analiz hatasi: {e}. Varsayilan 1080p60 kullaniliyor.")
            
            elif mode == "intro_loop" and intro_path and loop_path:
                try:
                    i_info = probe_video(intro_path)
                    l_info = probe_video(loop_path)
                    
                    if i_info.width == l_info.width and i_info.height == l_info.height:
                        target_width, target_height = i_info.width, i_info.height
                        # Use highest FPS or intro FPS? Let's stick to 60 for smoothness or intro FPS?
                        # User asked to keep resolution mainly.
                        # Let's keep 60fps default for smoothness unless they want source FPS too.
                        # "Otomatik 1080p @ 60fps" was the label.
                        # Let's keep 60fps but adapt resolution.
                        smart_res_found = True
                        print_success(f"Intro/Loop cozunurlugu eslesiyor: {target_width}x{target_height}. Resize yapilmadi.")
                    else:
                        print_info("Intro ve Loop cozunurlukleri farkli. 1080p standardi uygulaniyor.")
                except Exception as e:
                    print_warning(f"Analiz hatasi: {e}")

            if not smart_res_found:
                 print_info("Varsayilan 1080p60 ayarlari uygulaniyor.")

            codec_family = "av1"
            # Fallback if AV1 HW invalid? get_best_encoder handles it.
            codec_config = get_best_encoder(codec_family)
            print_info(f"Encoder: {codec_config.name}")
            
        else:
            # Codec selection for Orta/Gelismis/Ozel
            codec_options = [
                "AV1 (YouTube 1080p Premium master)",
                "H.264 (hizli encode, genis uyumluluk)",
                "H.265/HEVC (yuksek sikistirma)"
            ]
            if hw_available:
                hw_list = [k for k, v in available_encoders.items() if v]
                print_success(f"Hardware acceleration mevcut: {', '.join(hw_list)}")
                
            codec_idx = ask_choice("Hedef codec", codec_options, 1)
            codec_family = ["av1", "h264", "h265"][codec_idx - 1]
            codec_config = get_best_encoder(codec_family)
            
            # Mode Logic
            if config_mode_idx == 2: # Orta
                # Ask Resolution only
                res_choice = ask_choice("Cozunurluk", ["1080p (Full HD)", "1440p (2K)", "2160p (4K)", "Kaynak Cozunurlugu"], 1)
                if res_choice == 1: target_width, target_height = 1920, 1080
                elif res_choice == 2: target_width, target_height = 2560, 1440
                elif res_choice == 3: target_width, target_height = 3840, 2160
                elif res_choice == 4:
                    ref_path = single_video_path if mode == "single" else intro_path
                    ref_info = probe_video(ref_path)
                    target_width, target_height = ref_info.width, ref_info.height
                    
                print_info("Orta Mod: Diger ayarlar otomatik (60fps, Lanczos, 192k).")

            elif config_mode_idx >= 3: # Gelismis / Ozel
                # Resolution
                res_choice = ask_choice("Cozunurluk", ["1080p", "1440p", "2160p", "Kaynak", "Manuel Gir"], 1)
                if res_choice == 1: target_width, target_height = 1920, 1080
                elif res_choice == 2: target_width, target_height = 2560, 1440
                elif res_choice == 3: target_width, target_height = 3840, 2160
                elif res_choice == 4:
                    ref_path = single_video_path if mode == "single" else intro_path
                    ref_info = probe_video(ref_path)
                    target_width, target_height = ref_info.width, ref_info.height
                elif res_choice == 5:
                    target_width = ask_int("Genislik (px)", 100, 7680, 1920)
                    target_height = ask_int("Yukseklik (px)", 100, 4320, 1080)
                
                # FPS
                fps_choice = ask_choice("FPS", ["60", "30", "24", "Kaynak"], 1)
                if fps_choice == 1: target_fps = 60
                elif fps_choice == 2: target_fps = 30
                elif fps_choice == 3: target_fps = 24
                elif fps_choice == 4:
                     ref_path = single_video_path if mode == "single" else intro_path
                     ref_info = probe_video(ref_path)
                     target_fps = float(ref_info.fps.split('/')[0]) / float(ref_info.fps.split('/')[1]) if '/' in ref_info.fps else float(ref_info.fps)

                # Upscale Algo
                scale_algo = ask_choice("Upscale Algoritmasi", ["lanczos (Keskin/High Qual)", "bicubic (Standart)", "bilinear (Hizli)", "spline (Yumusak)"], 1)
                scale_algo = ["lanczos", "bicubic", "bilinear", "spline"][scale_algo-1]
                
                # Audio Bitrate
                audio_bitrate = ask_choice("Audio Bitrate", ["128k", "192k (Standart)", "256k", "320k (Yuksek)"], 2)
                audio_bitrate = ["128k", "192k", "256k", "320k"][audio_bitrate-1]
                
                if config_mode_idx == 4: # Ozel
                    # Ask about editing the command/header?
                    if ask_confirm("Varsayilan FFmpeg parametrelerini duzenlemek ister misiniz?"):
                        print_info("Not: Bu ozellik su anki surumde komut satirina yansitilacaktir.")
                        codec_config.preset = ask_text(f"Preset ({codec_config.preset})", codec_config.preset)
                        crf_val = ask_int(f"CRF/CQ ({codec_config.crf})", 0, 51, codec_config.crf)
                        codec_config.crf = crf_val
                    # Update extra args usually done inside CodecConfig, tricky to edit raw list here interactively
        
        print_info(f"Ayarlar: {target_width}x{target_height} @ {target_fps} fps | {scale_algo}")
        
        # ──────────────────────────────────────────────────────────────
        # Analysis & Compatibility Check
        # ──────────────────────────────────────────────────────────────
        console.print()
        print_info("Video/Codec Analizi yapiliyor...")
        
        # Helper to check
        # We assume 1920x1080 @ 60fps as target for now, or we could ask BEFORE.
        # But generally we want to standardize.
        temp_runner = FFmpegRunner()
        temp_encoder = VideoEncoder(
            temp_runner, codec_config,
            width=target_width, height=target_height, fps=target_fps
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
            return 2
        
        # Track selection
        console.print()
        print_audio_table(tracks, "Muzik Track'leri")
        
        track_mode = ask_choice("Track secimi", ["Hepsi (listedeki sirayla)", "Belirli track'leri sec"], 1)
        
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
            # Select track as BG (last option, or option 2 if no existing BGs)
            console.print()
            print_info("Track listesinden BG olarak kullanilacak parca secin:")
            print_audio_table(tracks, "Muzik Track'leri (BG olarak)")
            
            # Allow selecting tracks that are NOT in chosen_tracks to avoid confusion
            available_for_bg = tracks  # Could filter out chosen_tracks if desired
            
            indices = ask_multiple_choice(
                "BG olarak kullanilacak track(lar)",
                [p.name for p in available_for_bg],
                min_count=1
            )
            
            console.print()
            print_info("Secilen track'ler icin BG dB ayari:")
            for idx in indices:
                track = available_for_bg[idx - 1]
                db_str = ask_text(f"  {track.name} dB", "-8")  # Default -8 dB for BG
                try:
                    db = float(db_str)
                except ValueError:
                    db = -8.0
                chosen_bgs.append((track, db))
        
        # ──────────────────────────────────────────────────────────────
        # Audio Standardization
        # ──────────────────────────────────────────────────────────────
        console.print()
        if ask_confirm("Muzik dosyalarini otomatik normalize edip arsivlemek ister misiniz?", default=True):
            print_info("Muzik dosyalari standart (48kHz, 320k) formate donusturuluyor...")
            
            runner = FFmpegRunner(run_log)
            audio_processor = AudioProcessor(runner, tmp_dir)
            archive_dir = music_dir / "archive" # or just archive/ in root? User said "archived"
            
            def std_progress(name, current, total):
                console.print(f"  Processed {current}/{total}: {name}", end="\r")
            
            # Standardize Chosen Tracks
            # We standardize ALL relevant tracks just in case
            to_std = [t for t in chosen_tracks]
            new_tracks = audio_processor.standardize_tracks(to_std, archive_dir, std_progress)
            chosen_tracks = new_tracks # Update references
            
            # Update BGs if they are files (if from tracks, they are already processed in to_std if overlap)
            # This logic is tricky if BG is same as Track. 
            # standardize_tracks updates file in place basically (moves original).
            # So paths might point to new files automatically if names match.
            # But standardize_tracks returns new paths (same names). 
            # We should be safe.
            
            # Note: Backgrounds tuple is (Path, float).
            # We should standardize background files too if they are separate.
            bg_files = [b[0] for b in chosen_bgs if b[0] not in to_std]
            if bg_files:
                new_bgs = audio_processor.standardize_tracks(bg_files, archive_dir, std_progress)
                # Update chosen_bgs list with new paths?
                # Since standardize_tracks replaces file content at same path (mostly), 
                # or updates existing path, we might not need to update `chosen_bgs` tuples 
                # unless extension changed.
                # standardize_tracks logic: moves orig to archive, puts new at original path with .mp3.
                # If original was .wav, new is .mp3. Path object needs update.
                
                # Re-map chosen_bgs
                # Iterate and replace paths
                updated_bgs = []
                for b_path, b_db in chosen_bgs:
                    # Find if this path was standardized
                    # If it was in to_std or bg_files, it might have changed extension
                    # Check if file exists, if not, check .mp3 version
                    if not b_path.exists() and b_path.with_suffix(".mp3").exists():
                        updated_bgs.append((b_path.with_suffix(".mp3"), b_db))
                    else:
                        updated_bgs.append((b_path, b_db))
                chosen_bgs = updated_bgs
            
            print_success("Ses dosyalari standardize edildi.")

        # ──────────────────────────────────────────────────────────────
        # Drive Backup
        # ──────────────────────────────────────────────────────────────
        console.print()
        drive_enabled = False
        drive_folder_id = ""
        
        if ask_confirm("Render bitince videoyu Google Drive'a yedeklemek ister misiniz?"):
            drive_enabled = True
            drive_folder_id = ask_text("Drive Klasor ID (Bos = Root)", "")
            # Verify auth?
            try:
                from .drive import DriveUploader
                uploader = DriveUploader()
                if not uploader.authenticate():
                    print_warning("Drive girisi yapilamadi! Tarayicida dogrulama gerekebilir.")
                    print_info("Lutfen cikan linki takip edin veya credentials.json'i kontrol edin.")
            except ImportError:
                print_error("Drive modulu yuklenemedi!")
                drive_enabled = False

        # Output filename
        console.print()
        if mode == "single" and single_video_path:
            base_name = single_video_path.stem
            default_out = f"final_{base_name}_{codec_family}.mp4"
        else:
            default_out = f"final_{codec_family}_{dur_str.replace(':', 'h', 1).replace(':', 'm')}s.mp4"
        out_name = ask_text("Cikti dosyasi adi", default_out)
        
        # Sanitize filename (Fix for user copy-paste errors)
        import re
        safe_name = re.sub(r'[^\w\-. ]', '', out_name).strip()
        if not safe_name:
            safe_name = "output.mp4"
        if not safe_name.lower().endswith(".mp4"):
            safe_name += ".mp4"
            
        if safe_name != out_name:
            print_warning(f"Dosya adi duzeltildi: '{out_name}' -> '{safe_name}'")
            out_name = safe_name
            
        out_path = (base / out_name).resolve()
        
        # Post action
        console.print()
        post_action_idx = ask_choice(
            "Is bittikten sonra kaynak dosyalara ne olsun?",
            ["Oldugu gibi kalsin", "archive/ klasorune tasi", "Sil"],
            1
        )
        post_action = ["keep", "archive", "delete"][post_action_idx - 1]
        
        # Summary
        print_summary(
            intro_path, loop_path,
            codec_family, dur_str,
            chosen_tracks, chosen_bgs,
            out_path, post_action,
            single_video=single_video_path
        )
        
        if not ask_confirm("Devam edilsin mi?", True):
            print_warning("Iptal edildi.")
            return 0
        
        # ═══════════════════════════════════════════════════════════════════════
        # AUDIO VALIDATION
        # ═══════════════════════════════════════════════════════════════════════
        
        console.print()
        print_info("Muzik dosyalari dogrulaniyor...")
        
        runner = FFmpegRunner(run_log)
        audio_processor = AudioProcessor(runner, tmp_dir)
        
        def validation_progress(name: str, current: int, total: int):
            console.print(f"  [{current}/{total}] {name}...", end="\r")
        
        valid_tracks, invalid_tracks = audio_processor.validate_tracks(
            chosen_tracks, validation_progress
        )
        console.print()  # Clear the progress line
        
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
                    1
                )
                
                if choice == 2:
                    print_warning("Iptal edildi. Bozuk muzik dosyalarini degistirin.")
                    return 2
                
                # Update chosen tracks with valid ones only
                chosen_tracks = valid_tracks
                print_success(f"{len(valid_tracks)} gecerli track ile devam ediliyor.")
            else:
                print_error("Hic gecerli track yok! Muzik dosyalarini kontrol edin.")
                return 2
        else:
            print_success(f"Tum track'ler dogrulandi ({len(valid_tracks)} adet)")
            chosen_tracks = valid_tracks  # Use validated versions
        
        # Save session with validated tracks
        session = {
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "mode": mode,
            "intro": intro_path.resolve().as_posix() if intro_path else None,
            "loop": loop_path.resolve().as_posix() if loop_path else None,
            "video": single_video_path.resolve().as_posix() if single_video_path else None,
            "codec": codec_family,
            "encoder": codec_config.encoder,
            "duration": dur_str,
            "duration_sec": total_seconds,
            "tracks": [p.resolve().as_posix() for p in chosen_tracks],
            "tracks_validated": True,  # Mark as pre-validated
            "bgs": [{"path": p.resolve().as_posix(), "db": db} for p, db in chosen_bgs],
            "out": out_path.as_posix(),
            "post_action": post_action,
            "config": {
                "width": target_width,
                "height": target_height,
                "fps": target_fps,
                "scale_algo": scale_algo,
                "audio_bitrate": audio_bitrate,
                "drive_enabled": drive_enabled,
                "drive_folder_id": drive_folder_id
            }
        }
        session_json.write_text(json.dumps(session, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        
        # ═══════════════════════════════════════════════════════════════════════
        # RENDER PIPELINE
        # ═══════════════════════════════════════════════════════════════════════
        
        steps = [
            "Intro encode",
            "Loop encode",
            "Video concat",
            "Audio isleme",
            "Final mux"
        ]
        
        # Timing dictionary
        step_times = {}
        render_start = time.perf_counter()
        
        console.print()
        
        with MultiStepProgress(steps) as progress:
            
            # Step 1 & 2: Encode intro/loop
            encoder = VideoEncoder(
                runner=runner,
                codec_config=codec_config,
                width=target_width,
                height=target_height,
                fps=target_fps
            )
            
            intro_norm = tmp_dir / f"intro_norm_{codec_family}.mp4"
            loop_norm = tmp_dir / f"loop_norm_{codec_family}.mp4"
            video_only_single = tmp_dir / f"video_only_single_{codec_family}.mp4"
            
            def make_progress_callback(step_idx: int):
                def callback(p):
                    progress.update(step_idx, p.percent, speed=p.speed)
                return callback
            
            if mode == "single" and single_video_path:
                # Single video encode (no concat)
                t0 = time.perf_counter()
                video_only = encoder.normalize_video(
                    single_video_path, video_only_single, 
                    make_progress_callback(0),
                    scale_algo=scale_algo
                )
                step_times["Intro encode"] = time.perf_counter() - t0
                progress.complete_step(0)
                step_times["Loop encode"] = 0
                progress.complete_step(1)
                step_times["Video concat"] = 0
                progress.complete_step(2)
            else:
                # Encode intro
                t0 = time.perf_counter()
                encoder.normalize_video(intro_path, intro_norm, make_progress_callback(0), scale_algo=scale_algo)
                step_times["Intro encode"] = time.perf_counter() - t0
                progress.complete_step(0)
                
                # Encode loop
                t0 = time.perf_counter()
                encoder.normalize_video(loop_path, loop_norm, make_progress_callback(1), scale_algo=scale_algo)
                step_times["Loop encode"] = time.perf_counter() - t0
                progress.complete_step(1)
                
                # Step 3: Concat
                t0 = time.perf_counter()
                video_only = encoder.concat_videos(
                    intro_norm, loop_norm,
                    total_seconds, tmp_dir,
                    make_progress_callback(2)
                )
                step_times["Video concat"] = time.perf_counter() - t0
                progress.complete_step(2)
            
            # Step 4: Audio (tracks already validated above)
            t0 = time.perf_counter()
            music_loop = audio_processor.create_music_loop(
                chosen_tracks, total_seconds, pre_validated=True
            )
            
            if chosen_bgs:
                bg_processed = audio_processor.process_backgrounds(chosen_bgs)
                audio_full = audio_processor.mix_tracks(
                    music_loop, bg_processed, total_seconds
                )
            else:
                audio_full = music_loop
            
            step_times["Audio isleme"] = time.perf_counter() - t0
            progress.complete_step(3)
            
            # Step 5: Final mux
            t0 = time.perf_counter()
            mux_video_audio(
                runner, video_only, audio_full, out_path,
                audio_bitrate=audio_bitrate,
                progress_callback=make_progress_callback(4)
            )
            step_times["Final mux"] = time.perf_counter() - t0
            progress.complete_step(4)
        
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
        
        # Completion with detailed timing
        final_duration = get_duration(out_path)
        
        console.print()
        console.print("=" * 60)
        console.print("[bold green]RENDER TAMAMLANDI[/]")
        console.print("=" * 60)
        console.print(f"[bold]Dosya:[/] {out_path.name}")
        console.print(f"[bold]Video Suresi:[/] {final_duration:.1f} saniye ({final_duration/3600:.2f} saat)")
        console.print()
        console.print("[bold yellow]ADIM SURELERI:[/]")
        for step_name, step_time in step_times.items():
            if step_time > 0:
                mins = int(step_time // 60)
                secs = int(step_time % 60)
                console.print(f"  {step_name}: {mins}m {secs}s")
        console.print()
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
        
        # ──────────────────────────────────────────────────────────────
        # Drive Upload
        # ──────────────────────────────────────────────────────────────
        if drive_enabled:
            console.print()
            print_info("Google Drive'a yukleniyor...")
            
            try:
                from .drive import DriveUploader
                uploader = DriveUploader()
                success, file_id = uploader.upload_file(out_path, drive_folder_id if drive_folder_id else None)
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
        """
    )
    
    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"Video Renderer {__version__}"
    )
    
    parser.add_argument(
        "--list-hw",
        action="store_true",
        help="Kullanilabilir hardware encoder'lari listele"
    )
    
    parser.add_argument(
        "--resume", "-r",
        action="store_true",
        help="Son session'dan kaldigi yerden devam et"
    )
    
    parser.add_argument(
        "--no-loop",
        action="store_true",
        help="Hata durumunda donguye girmeden cik"
    )
    
    parser.add_argument(
        "--tui",
        action="store_true",
        help="Yeni Textual TUI arayuzunu kullan"
    )
    
    args = parser.parse_args()
    
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
        return run_tui()
    
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
                        [
                            "Kaldigi yerden devam et",
                            "Yeni render baslat",
                            "Cikis"
                        ],
                        1
                    )
                    
                    if choice == 1:
                        result = run_resume()
                        if result == 0:
                            # Success - ask what to do next
                            console.print()
                            next_choice = ask_choice(
                                "Render tamamlandi! Ne yapmak istersiniz?",
                                ["Yeni render baslat", "Cikis"],
                                2
                            )
                            if next_choice == 2:
                                return 0
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
            result = run_interactive()
            
            if result == 0:
                # Success
                console.print()
                next_choice = ask_choice(
                    "Render tamamlandi! Ne yapmak istersiniz?",
                    ["Yeni render baslat", "Cikis"],
                    2
                )
                if next_choice == 2:
                    return 0
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
                [
                    "Kaldigi yerden devam et (--resume)",
                    "Yeni render baslat",
                    "Cikis"
                ],
                1
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

