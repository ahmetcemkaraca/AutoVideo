#!/usr/bin/env python3
"""
Sleep Video Renderer - VPS Edition
====================================
Katmanlar (üstten alta):
  [VIDEO]    intro.mp4 → loop.mp4 x N  (toplam 8-10 saat)
  [MÜZİK]    music/ klasöründeki dosyalar rastgele sırayla, süre dolana kadar
  [AMBIYANS]  bg sesler aynı anda çalar, dosya adındaki dB'e göre ayarlı

Kullanım:
  python sleep_video_render.py \
      --intro intro.mp4 \
      --loop  loop.mp4 \
      --music-dir ./music \
      --bg-sounds fire-3db.mp3 rain.mp3 crickets+1.5db.mp3 \
      --output output.mp4

Dosya adı kuralı (dB):
  fire-3db.mp3    → -3 dB kısılır
  rain+2db.mp3    → +2 dB yükseltilir
  birds.mp3       → değişmez (0 dB)
"""

import argparse
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time

# ─────────────────────────────────────────────────────────────────────────────
# Yardımcı fonksiyonlar
# ─────────────────────────────────────────────────────────────────────────────

def run(cmd: list, desc: str = "", check: bool = True) -> subprocess.CompletedProcess:
    print(f"\n▶  {desc or ' '.join(str(c) for c in cmd[:5])}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print("─── STDERR ──────────────────────────────")
        print(result.stderr[-4000:])
        print("─────────────────────────────────────────")
        sys.exit(1)
    return result


def probe(filepath: str) -> dict:
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        filepath,
    ]
    r = run(cmd, f"probe: {os.path.basename(filepath)}", check=False)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        print(f"HATA: {filepath} okunamadı.")
        sys.exit(1)


def get_duration(filepath: str) -> float:
    return float(probe(filepath)["format"]["duration"])


def get_video_props(filepath: str) -> dict:
    for s in probe(filepath).get("streams", []):
        if s.get("codec_type") == "video":
            fps_str = s.get("r_frame_rate", "30/1")
            n, d = fps_str.split("/")
            return {
                "codec_name": s.get("codec_name"),
                "width":      s.get("width"),
                "height":     s.get("height"),
                "fps":        round(float(n) / float(d), 3),
                "pix_fmt":    s.get("pix_fmt", "yuv420p"),
            }
    return {}


def has_audio_stream(filepath: str) -> bool:
    for s in probe(filepath).get("streams", []):
        if s.get("codec_type") == "audio":
            return True
    return False


def parse_db(filename: str) -> float:
    """
    Dosya / klasör adından dB değeri oku.
      fire-3db.mp3   → -3.0
      rain+1.5db.mp3 → +1.5
      birds.mp3      → 0.0
      ambient3db.mp3 → -3.0  (işaret yok → negatif varsayım)
    """
    name = os.path.basename(filename)
    m = re.search(r"([+\-]\d+(?:\.\d+)?)db", name, re.IGNORECASE)
    if m:
        return float(m.group(1))
    m2 = re.search(r"(\d+(?:\.\d+)?)db", name, re.IGNORECASE)
    if m2:
        return -float(m2.group(1))
    return 0.0


def db_to_amp(db: float) -> float:
    return 10 ** (db / 20.0)


def hms(s: float) -> str:
    h  = int(s // 3600)
    m  = int((s % 3600) // 60)
    sc = s % 60
    return f"{h:02d}:{m:02d}:{sc:05.2f}"


AUDIO_EXTS = {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".opus"}


def collect_music(music_dir: str) -> list:
    """Klasördeki ses dosyalarını topla, rastgele karıştır."""
    files = [
        os.path.join(music_dir, f)
        for f in sorted(os.listdir(music_dir))
        if os.path.splitext(f)[1].lower() in AUDIO_EXTS
    ]
    if not files:
        print(f"HATA: {music_dir} içinde ses dosyası yok.")
        sys.exit(1)
    random.shuffle(files)
    return files


# ─────────────────────────────────────────────────────────────────────────────
# Müzik playlist — shuffle + loop to duration
# ─────────────────────────────────────────────────────────────────────────────

def build_music_track(music_files: list, target_sec: float, tmp: str,
                      audio_bitrate: str) -> str:
    """
    Müzikleri karıştırılmış sırada birleştir, hedef süreyi doldur.
    Playlist biterse baştan başlar (yine shuffle'lı).
    """
    print(f"\n  Playlist ({len(music_files)} parça, shuffle):")
    for f in music_files:
        print(f"    {os.path.basename(f)}")

    # Playlist'i ihtiyaç kadar uzat
    playlist  = list(music_files)
    total_dur = sum(get_duration(f) for f in playlist)
    while total_dur < target_sec:
        extra = list(music_files)
        random.shuffle(extra)
        playlist  += extra
        total_dur += sum(get_duration(f) for f in extra)

    concat_txt = os.path.join(tmp, "music_list.txt")
    with open(concat_txt, "w") as fp:
        for f in playlist:
            fp.write(f"file '{os.path.abspath(f)}'\n")

    music_out = os.path.join(tmp, "music_full.aac")
    run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_txt,
        "-t", str(target_sec),
        "-c:a", "aac", "-b:a", audio_bitrate,
        music_out,
    ], "Müzik track birleştiriliyor")

    return music_out


# ─────────────────────────────────────────────────────────────────────────────
# Ana render
# ─────────────────────────────────────────────────────────────────────────────

def render(args):
    t0 = time.time()

    # Hedef süre
    if args.target_hours:
        target_sec = args.target_hours * 3600.0
    else:
        target_sec = random.uniform(8.0, 10.0) * 3600.0

    print(f"\n{'='*60}")
    print(f"  🎬  Sleep Video Renderer")
    print(f"  Hedef süre   : {hms(target_sec)}  ({target_sec/3600:.2f} h)")
    print(f"  Intro        : {args.intro}")
    print(f"  Loop         : {args.loop}")
    print(f"  Music dir    : {args.music_dir or '(yok)'}")
    if args.bg_sounds:
        print(f"  Ambiyans     : {', '.join(os.path.basename(b) for b in args.bg_sounds)}")
    print(f"  Çıktı        : {args.output}")
    print(f"{'='*60}\n")

    intro_dur   = get_duration(args.intro)
    loop_dur    = get_duration(args.loop)
    intro_props = get_video_props(args.intro)
    loop_props  = get_video_props(args.loop)

    print(f"Intro süresi : {hms(intro_dur)}")
    print(f"Loop süresi  : {hms(loop_dur)}")

    body_sec   = target_sec - intro_dur
    loop_count = int(body_sec / loop_dur) + 2

    same_fmt = (
        intro_props.get("codec_name") == loop_props.get("codec_name") and
        intro_props.get("width")      == loop_props.get("width")      and
        intro_props.get("height")     == loop_props.get("height")
    )
    use_copy = same_fmt and not args.force_reencode
    print(f"Video codec  : {'copy (re-encode yok)' if use_copy else args.vcodec}")
    print(f"Loop tekrar  : {loop_count}x  (~{hms(loop_dur * loop_count)})")

    with tempfile.TemporaryDirectory() as tmp:

        # ──────────────────────────────────────────────────────────────────
        # ADIM 1 — Loop video
        # ──────────────────────────────────────────────────────────────────
        print(f"\n[1/4] Loop video oluşturuluyor...")
        looped = os.path.join(tmp, "looped.mp4")
        px = intro_props.get("pix_fmt", "yuv420p")

        lc = ["ffmpeg", "-y",
              "-stream_loop", str(loop_count - 1),
              "-i", args.loop,
              "-t", str(body_sec)]
        if use_copy:
            lc += ["-c", "copy"]
        else:
            lc += ["-c:v", args.vcodec, "-preset", args.preset,
                   "-crf", str(args.crf), "-pix_fmt", px,
                   "-c:a", "aac", "-b:a", args.audio_bitrate]
        lc += [looped]
        run(lc, "Loop video")

        # ──────────────────────────────────────────────────────────────────
        # ADIM 2 — Video concat (intro + looped)
        # ──────────────────────────────────────────────────────────────────
        print(f"\n[2/4] Intro + loop birleştiriliyor (video)...")
        concat_vid = os.path.join(tmp, "concat.mp4")

        list_txt = os.path.join(tmp, "list.txt")
        with open(list_txt, "w") as f:
            f.write(f"file '{os.path.abspath(args.intro)}'\n")
            f.write(f"file '{os.path.abspath(looped)}'\n")

        cc = ["ffmpeg", "-y",
              "-f", "concat", "-safe", "0",
              "-i", list_txt,
              "-t", str(target_sec)]
        if use_copy:
            cc += ["-c", "copy"]
        else:
            cc += ["-c:v", args.vcodec, "-preset", args.preset,
                   "-crf", str(args.crf), "-pix_fmt", px,
                   "-c:a", "aac", "-b:a", args.audio_bitrate]
        cc += [concat_vid]
        run(cc, "Concat intro+loop")

        # ──────────────────────────────────────────────────────────────────
        # ADIM 3 — Müzik playlist
        # ──────────────────────────────────────────────────────────────────
        music_track = None
        if args.music_dir:
            print(f"\n[3/4] Müzik playlist hazırlanıyor...")
            music_files = collect_music(args.music_dir)
            music_track = build_music_track(
                music_files, target_sec, tmp, args.audio_bitrate
            )
        else:
            print(f"\n[3/4] music-dir verilmedi → müzik katmanı yok.")

        # ──────────────────────────────────────────────────────────────────
        # ADIM 4 — Final mix
        #
        # Katman önceliği (amix normalize=0):
        #   [orig]    — intro + loop video'nun kendi sesi (varsa)
        #   [music]   — müzik playlist
        #   [amb0..N] — ambiyans sesleri (aynı anda, dB ayarlı)
        # ──────────────────────────────────────────────────────────────────
        print(f"\n[4/4] Final ses mixi & encode...")

        cmd_inputs = ["-i", concat_vid]
        input_idx  = 1

        music_idx = None
        if music_track:
            # stream_loop -1: müzik dosyası kısa kalırsa sonsuz döngü
            # (build_music_track zaten yeterince uzatıyor ama garanti)
            cmd_inputs += ["-stream_loop", "-1", "-i", music_track]
            music_idx   = input_idx
            input_idx  += 1

        bg_indices = []
        for bg in args.bg_sounds:
            cmd_inputs += ["-stream_loop", "-1", "-i", bg]
            bg_indices.append(input_idx)
            input_idx  += 1

        filters  = []
        mix_srcs = []

        # Orijinal video sesi (intro'nun kendi müziği)
        if has_audio_stream(concat_vid):
            filters.append("[0:a]volume=1.0[orig]")
            mix_srcs.append("[orig]")

        # Müzik katmanı — ayrı bir katman, volume ayarı klasör adından
        if music_track and music_idx is not None:
            db_m  = parse_db(args.music_dir)   # klasör adına -3db yazılabilir
            amp_m = db_to_amp(db_m)
            filters.append(f"[{music_idx}:a]volume={amp_m:.6f}[music]")
            mix_srcs.append("[music]")
            print(f"  Müzik katmanı   dB={db_m:+.1f}  amp={amp_m:.4f}")

        # Ambiyans katmanları
        for i, (bg, idx) in enumerate(zip(args.bg_sounds, bg_indices)):
            db  = parse_db(bg)
            amp = db_to_amp(db)
            lbl = f"[amb{i}]"
            filters.append(f"[{idx}:a]volume={amp:.6f}{lbl}")
            mix_srcs.append(lbl)
            print(f"  Ambiyans: {os.path.basename(bg):40s}  dB={db:+.1f}  amp={amp:.4f}")

        if not mix_srcs:
            # Hiç ses kaynağı yok — video'yu olduğu gibi kopyala
            print("  Ses kaynağı yok, video kopyalanıyor.")
            shutil.copy(concat_vid, args.output)
        else:
            n = len(mix_srcs)
            srcs = "".join(mix_srcs)

            if n == 1:
                filters.append(f"{mix_srcs[0]}acopy[aout]")
            else:
                # normalize=0 → ana müzik sesi ezilmez
                filters.append(
                    f"{srcs}amix=inputs={n}:duration=first:normalize=0[aout]"
                )

            final_cmd = [
                "ffmpeg", "-y",
                *cmd_inputs,
                "-filter_complex", ";".join(filters),
                "-map", "0:v",
                "-map", "[aout]",
                "-t", str(target_sec),
                "-c:v", "copy",          # video zaten encode edildi, tekrar dokunma
                "-c:a", "aac", "-b:a", args.audio_bitrate,
                args.output,
            ]
            run(final_cmd, "Final mix")

    # Özet
    elapsed  = time.time() - t0
    out_size = os.path.getsize(args.output) / (1024 ** 3)
    out_dur  = get_duration(args.output)

    print(f"\n{'='*60}")
    print(f"  ✅  Tamamlandı!")
    print(f"  Çıktı süresi : {hms(out_dur)}  ({out_dur/3600:.2f} h)")
    print(f"  Dosya boyutu : {out_size:.2f} GB")
    print(f"  Geçen süre   : {hms(elapsed)}")
    print(f"  Dosya        : {args.output}")
    print(f"{'='*60}\n")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="8-10 Saat Uyku Videosu Render Aracı",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
ÖRNEK:
  python sleep_video_render.py \\
      --intro    intro.mp4 \\
      --loop     loop.mp4 \\
      --music-dir ./music \\
      --bg-sounds fire-3db.mp3 rain.mp3 wind+1db.mp3 \\
      --output   output.mp4

KLASÖR YAPISI:
  proje/
  ├── sleep_video_render.py
  ├── intro.mp4
  ├── loop.mp4
  ├── music/           ← tüm müzikleri buraya at
  │   ├── track1.mp3
  │   ├── track2.mp3
  │   └── track3.mp3
  ├── fire-3db.mp3     ← ambiyans (dosya adıyla dB ayarı)
  ├── rain.mp3
  └── output.mp4

dB KURALI (dosya veya klasör adında):
  fire-3db.mp3   → -3 dB (kısık)
  rain+2db.mp3   → +2 dB (yüksek)
  birds.mp3      → değişmez
  music-2db/     → klasörün tamamına -2 dB uygulanır
        """,
    )
    parser.add_argument("--intro",         required=True,
                        help="Intro video (CapCut'tan)")
    parser.add_argument("--loop",          required=True,
                        help="Loop video (CapCut'tan)")
    parser.add_argument("--output",        required=True,
                        help="Çıktı dosyası (örn: output.mp4)")
    parser.add_argument("--music-dir",     default=None, metavar="DIR",
                        help="Müzik klasörü — rastgele playlist yapılır, ayrı katman")
    parser.add_argument("--bg-sounds",     nargs="*", default=[], metavar="SES",
                        help="Ambiyans sesleri — aynı anda çalar, müziğin altında")
    parser.add_argument("--target-hours",  type=float, default=None,
                        help="Hedef süre (saat). Verilmezse 8-10 arası rastgele.")
    parser.add_argument("--vcodec",        default="libx264")
    parser.add_argument("--preset",        default="fast",
                        choices=["ultrafast","superfast","veryfast","faster",
                                 "fast","medium","slow","veryslow"])
    parser.add_argument("--crf",           type=int, default=18)
    parser.add_argument("--audio-bitrate", default="192k")
    parser.add_argument("--force-reencode", action="store_true",
                        help="Video'yu her zaman yeniden encode et")

    args = parser.parse_args()

    for f in [args.intro, args.loop]:
        if not os.path.isfile(f):
            print(f"HATA: Dosya yok: {f}")
            sys.exit(1)
    for f in args.bg_sounds or []:
        if not os.path.isfile(f):
            print(f"HATA: Ambiyans yok: {f}")
            sys.exit(1)
    if args.music_dir and not os.path.isdir(args.music_dir):
        print(f"HATA: music-dir yok: {args.music_dir}")
        sys.exit(1)
    if shutil.which("ffmpeg") is None:
        print("HATA: ffmpeg yok → apt install ffmpeg")
        sys.exit(1)

    render(args)


if __name__ == "__main__":
    main()
