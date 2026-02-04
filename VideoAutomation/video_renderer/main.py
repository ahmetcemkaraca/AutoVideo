#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main entry point for video renderer application.
"""

import json
import sys
import time
import traceback
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
    print_warning, print_info, MultiStepProgress
)


# ═══════════════════════════════════════════════════════════════════════════════
# File Discovery
# ═══════════════════════════════════════════════════════════════════════════════

def list_video_files(base: Path) -> List[Tuple[Path, VideoInfo]]:
    """List video files with their info."""
    files = []
    for p in sorted(base.iterdir()):
        if not p.is_file():
            continue
        if p.name.startswith("final_") or p.name.startswith("video_only"):
            continue
        if p.suffix.lower() in VIDEO_EXTENSIONS:
            try:
                info = probe_video(p)
                files.append((p, info))
            except Exception:
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
    
    raise ValueError("Format HH:MM:SS veya MM:SS olmalı (örn: 08:06:07 veya 30:00)")


def format_duration(seconds: int) -> str:
    """Format seconds to HH:MM:SS."""
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


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
        
        # Check music dir
        if not music_dir.exists():
            print_error("music/ klasörü bulunamadı!")
            print_info("render/music oluşturun ve müzikleri içine koyun.")
            return 2
        
        # List videos
        videos = list_video_files(base)
        if len(videos) < 2:
            print_error("En az 2 video gerekli (intro ve loop)!")
            print_info("render/ klasörüne intro ve loop video dosyalarını koyun.")
            return 2
        
        print_video_table(videos)
        
        # Select intro/loop
        intro_idx = ask_int("INTRO hangisi?", 1, len(videos))
        loop_idx = ask_int("LOOP hangisi?", 1, len(videos))
        
        if intro_idx == loop_idx:
            print_error("Intro ve loop aynı dosya olamaz!")
            return 2
        
        intro_path, intro_info = videos[intro_idx - 1]
        loop_path, loop_info = videos[loop_idx - 1]
        
        # Show detailed info
        print_video_info_panel("INTRO", intro_path, intro_info)
        print_video_info_panel("LOOP", loop_path, loop_info)
        
        # Codec selection
        console.print()
        available_encoders = detect_available_encoders()
        hw_available = any(available_encoders.values())
        
        codec_options = [
            "AV1 (YouTube 1080p Premium master)",
            "H.264 (hızlı encode, geniş uyumluluk)",
            "H.265/HEVC (yüksek sıkıştırma)"
        ]
        
        if hw_available:
            hw_list = [k for k, v in available_encoders.items() if v]
            print_success(f"Hardware acceleration mevcut: {', '.join(hw_list)}")
        
        codec_idx = ask_choice("Hedef codec", codec_options, 1)
        codec_family = ["av1", "h264", "h265"][codec_idx - 1]
        
        # Get codec config (with HW acceleration if available)
        codec_config = get_best_encoder(codec_family)
        print_info(f"Kullanılacak encoder: {codec_config.name} ({codec_config.encoder})")
        
        # Duration
        console.print()
        while True:
            dur_str = ask_text("Hedef süre (HH:MM:SS)", "08:00:00")
            try:
                total_seconds = parse_duration(dur_str)
                break
            except ValueError as e:
                print_error(str(e))
        
        # Audio files
        tracks, backgrounds = list_audio_files(music_dir)
        
        if not tracks:
            print_error("music/ içinde track bulunamadı!")
            return 2
        
        # Track selection
        console.print()
        print_audio_table(tracks, "Müzik Track'leri")
        
        track_mode = ask_choice("Track seçimi", ["Hepsi (listedeki sırayla)", "Belirli track'leri seç"], 1)
        
        if track_mode == 1:
            chosen_tracks = tracks
        else:
            indices = ask_multiple_choice("Track seç", [p.name for p in tracks])
            chosen_tracks = [tracks[i - 1] for i in indices]
        
        # Background selection
        chosen_bgs: List[Tuple[Path, float]] = []
        
        console.print()
        print_info("Background ses seçenekleri:")
        
        bg_options = ["BG kullanma"]
        if backgrounds:
            bg_options.append(f"Mevcut BG dosyalarından seç ({len(backgrounds)} adet)")
        bg_options.append("Track listesinden BG olarak kullan")
        
        bg_mode = ask_choice("Background seçimi", bg_options, 1)
        
        if bg_mode == 1:
            # No BG
            pass
        
        elif bg_mode == 2 and backgrounds:
            # Select from existing BG files
            print_audio_table(backgrounds, "Background Sesler")
            
            select_mode = ask_choice("BG seçimi", ["Hepsi", "Belirli BG'leri seç"], 1)
            
            if select_mode == 1:
                selected_bgs = backgrounds
            else:
                indices = ask_multiple_choice("BG seç", [p.name for p in backgrounds])
                selected_bgs = [backgrounds[i - 1] for i in indices]
            
            # Get dB for each
            console.print()
            print_info("Seçilen BG'ler için dB ayarı (Enter = varsayılan):")
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
            print_info("Track listesinden BG olarak kullanılacak parça seçin:")
            print_audio_table(tracks, "Müzik Track'leri (BG olarak)")
            
            # Allow selecting tracks that are NOT in chosen_tracks to avoid confusion
            available_for_bg = tracks  # Could filter out chosen_tracks if desired
            
            indices = ask_multiple_choice(
                "BG olarak kullanılacak track(lar)",
                [p.name for p in available_for_bg],
                min_count=1
            )
            
            console.print()
            print_info("Seçilen track'ler için BG dB ayarı:")
            for idx in indices:
                track = available_for_bg[idx - 1]
                db_str = ask_text(f"  {track.name} dB", "-8")  # Default -8 dB for BG
                try:
                    db = float(db_str)
                except ValueError:
                    db = -8.0
                chosen_bgs.append((track, db))
        
        # Output filename
        console.print()
        default_out = f"final_{codec_family}_{dur_str.replace(':', 'h', 1).replace(':', 'm')}s.mp4"
        out_name = ask_text("Çıktı dosyası adı", default_out)
        out_path = (base / out_name).resolve()
        
        # Post action
        console.print()
        post_action_idx = ask_choice(
            "İş bittikten sonra kaynak dosyalara ne olsun?",
            ["Olduğu gibi kalsın", "archive/ klasörüne taşı", "Sil"],
            1
        )
        post_action = ["keep", "archive", "delete"][post_action_idx - 1]
        
        # Summary
        print_summary(
            intro_path, loop_path,
            codec_family, dur_str,
            chosen_tracks, chosen_bgs,
            out_path, post_action
        )
        
        if not ask_confirm("Devam edilsin mi?", True):
            print_warning("İptal edildi.")
            return 0
        
        # Save session
        session = {
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "intro": intro_path.resolve().as_posix(),
            "loop": loop_path.resolve().as_posix(),
            "codec": codec_family,
            "encoder": codec_config.encoder,
            "duration": dur_str,
            "duration_sec": total_seconds,
            "tracks": [p.resolve().as_posix() for p in chosen_tracks],
            "bgs": [{"path": p.resolve().as_posix(), "db": db} for p, db in chosen_bgs],
            "out": out_path.as_posix(),
            "post_action": post_action,
        }
        session_json.write_text(json.dumps(session, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        
        # ═══════════════════════════════════════════════════════════════════════
        # RENDER PIPELINE
        # ═══════════════════════════════════════════════════════════════════════
        
        runner = FFmpegRunner(run_log)
        
        steps = [
            "Intro encode",
            "Loop encode",
            "Video concat",
            "Audio işleme",
            "Final mux"
        ]
        
        console.print()
        
        with MultiStepProgress(steps) as progress:
            
            # Step 1 & 2: Encode intro/loop
            encoder = VideoEncoder(
                runner=runner,
                codec_config=codec_config,
                width=1920,
                height=1080,
                fps=60
            )
            
            intro_norm = tmp_dir / f"intro_norm_{codec_family}.mp4"
            loop_norm = tmp_dir / f"loop_norm_{codec_family}.mp4"
            
            def make_progress_callback(step_idx: int):
                def callback(p):
                    progress.update(step_idx, p.percent)
                return callback
            
            # Encode intro
            encoder.normalize_video(intro_path, intro_norm, make_progress_callback(0))
            progress.complete_step(0)
            
            # Encode loop
            encoder.normalize_video(loop_path, loop_norm, make_progress_callback(1))
            progress.complete_step(1)
            
            # Step 3: Concat
            video_only = encoder.concat_videos(
                intro_norm, loop_norm,
                total_seconds, tmp_dir,
                make_progress_callback(2)
            )
            progress.complete_step(2)
            
            # Step 4: Audio
            audio_processor = AudioProcessor(runner, tmp_dir)
            
            music_loop = audio_processor.create_music_loop(
                chosen_tracks, total_seconds
            )
            
            if chosen_bgs:
                bg_processed = audio_processor.process_backgrounds(chosen_bgs)
                audio_full = audio_processor.mix_tracks(
                    music_loop, bg_processed, total_seconds
                )
            else:
                audio_full = music_loop
            
            progress.complete_step(3)
            
            # Step 5: Final mux
            mux_video_audio(
                runner, video_only, audio_full, out_path,
                progress_callback=make_progress_callback(4)
            )
            progress.complete_step(4)
        
        # Completion
        final_duration = get_duration(out_path)
        print_completion(out_path, final_duration)
        
        # Post action
        if post_action == "delete":
            try:
                intro_path.unlink(missing_ok=True)
                loop_path.unlink(missing_ok=True)
                print_success("Kaynak intro/loop silindi.")
            except Exception as e:
                print_warning(f"Kaynak silme hatası: {e}")
        
        elif post_action == "archive":
            archive_dir = base / "archive" / time.strftime("%Y%m%d_%H%M%S")
            archive_dir.mkdir(parents=True, exist_ok=True)
            try:
                intro_path.rename(archive_dir / intro_path.name)
                loop_path.rename(archive_dir / loop_path.name)
                print_success(f"Kaynak intro/loop arşivlendi: {archive_dir.as_posix()}")
            except Exception as e:
                print_warning(f"Arşivleme hatası: {e}")
        
        return 0
    
    except KeyboardInterrupt:
        console.print()
        print_warning("Kullanıcı tarafından iptal edildi.")
        return 130
    
    except Exception as e:
        tb = traceback.format_exc()
        msg = f"# ERROR — {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n{tb}\n"
        err_log.write_text(msg, encoding="utf-8")
        
        console.print()
        print_error(f"Hata oluştu: {e}")
        print_info(f"Detaylar: {err_log.as_posix()}")
        return 4


# ═══════════════════════════════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> int:
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Video Renderer - Intro+Loop video birleştirme ve ses miksajı",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Örnekler:
  python -m video_renderer              # İnteraktif mod
  python -m video_renderer --version    # Versiyon göster
  python -m video_renderer --list-hw    # HW encoder'ları listele
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
        help="Kullanılabilir hardware encoder'ları listele"
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
    
    return run_interactive()


if __name__ == "__main__":
    raise SystemExit(main())
