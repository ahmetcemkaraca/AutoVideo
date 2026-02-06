#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate test video fixtures for validation testing.

This script creates various test videos with different specifications
using FFmpeg for testing the AutoVideo validation system.

Test videos include:
- Valid videos (different resolutions, codecs, FPS)
- Invalid videos (wrong FPS, wrong resolution, no audio, corrupted)
- Edge case videos (very short, very long)
"""

import subprocess
import sys
from pathlib import Path
from typing import Optional
import shutil


# Configuration
FIXTURES_DIR = Path(__file__).parent / "videos"
FFMPEG_PATH = shutil.which("ffmpeg")

# Default video settings for valid test videos
DEFAULT_WIDTH = 1920
DEFAULT_HEIGHT = 1080
DEFAULT_FPS = 60
DEFAULT_DURATION = 10  # seconds


def check_ffmpeg() -> bool:
    """Check if FFmpeg is available."""
    if FFMPEG_PATH is None:
        print("[ERROR] FFmpeg bulunamadi. Lutfen FFmpeg'i yükleyin ve PATH'e ekleyin.")
        return False
    return True


def generate_test_video(
    output_path: Path,
    duration: int = DEFAULT_DURATION,
    resolution: str = "1920x1080",
    fps: int = DEFAULT_FPS,
    codec: str = "libx264",
    pixel_format: str = "yuv420p",
    with_audio: bool = True,
    audio_freq: int = 440,
    extra_args: Optional[list] = None,
) -> bool:
    """
    Generate a test video using FFmpeg.

    Args:
        output_path: Output file path
        duration: Duration in seconds
        resolution: Resolution string (WxH)
        fps: Frames per second
        codec: Video codec
        pixel_format: Pixel format
        with_audio: Include audio track
        audio_freq: Audio frequency in Hz (for test tone)
        extra_args: Extra FFmpeg arguments

    Returns:
        True if successful, False otherwise
    """
    cmd = [
        "ffmpeg",
        "-y",  # Overwrite output
        "-f", "lavfi",
        "-i", f"color=c=black:s={resolution}:d={duration}",  # Video input
    ]

    if with_audio:
        cmd.extend([
            "-f", "lavfi",
            "-i", f"sine=frequency={audio_freq}:sample_rate=48000:duration={duration}",  # Audio input
        ])

    cmd.extend([
        "-c:v", codec,
        "-preset", "fast",
        "-crf", "23",
        "-pix_fmt", pixel_format,
        "-r", str(fps),
        "-movflags", "+faststart",
    ])

    if extra_args:
        cmd.extend(extra_args)

    if with_audio:
        cmd.extend([
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
        ])
    else:
        cmd.append("-an")  # No audio

    cmd.append(str(output_path))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=120
        )
        print(f"  [OK] {output_path.name}")
        return True
    except subprocess.TimeoutExpired:
        print(f"  [TIMEOUT] {output_path.name}")
        return False
    except subprocess.CalledProcessError as e:
        print(f"  [FAILED] {output_path.name}: {e.stderr[:200] if e.stderr else 'Unknown error'}")
        return False


def create_valid_videos() -> None:
    """Create valid test videos for positive testing."""
    print("\n[INFO] Geçerli test videolari oluşturuluyor...")

    # Valid 1080p60 H.264 video
    generate_test_video(
        FIXTURES_DIR / "valid_1080p60_h264.mp4",
        duration=10,
        resolution="1920x1080",
        fps=60,
        codec="libx264",
    )

    # Valid 720p30 H.264 video
    generate_test_video(
        FIXTURES_DIR / "valid_720p30_h264.mp4",
        duration=10,
        resolution="1280x720",
        fps=30,
        codec="libx264",
    )

    # Valid 1080p60 H.265/HEVC video
    generate_test_video(
        FIXTURES_DIR / "valid_1080p60_h265.mp4",
        duration=10,
        resolution="1920x1080",
        fps=60,
        codec="libx265",
    )

    # Valid 1080p60 AV1 video (if available)
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if "libsvtav1" in result.stdout:
            generate_test_video(
                FIXTURES_DIR / "valid_1080p60_av1.mp4",
                duration=10,
                resolution="1920x1080",
                fps=60,
                codec="libsvtav1",
            )
    except Exception:
        pass  # Skip AV1 if not available

    # Valid 59.94 FPS video (30000/1001)
    generate_test_video(
        FIXTURES_DIR / "valid_1080p59_94_h264.mp4",
        duration=10,
        resolution="1920x1080",
        fps=59.94,
        codec="libx264",
        extra_args=["-r", "30000/1001"],
    )

    # Long video (1 minute)
    generate_test_video(
        FIXTURES_DIR / "valid_1080p60_h264_1min.mp4",
        duration=60,
        resolution="1920x1080",
        fps=60,
        codec="libx264",
    )


def create_invalid_videos() -> None:
    """Create invalid test videos for negative testing."""
    print("\n[INFO] Geçersiz test videolari oluşturuluyor...")

    # Video with missing audio
    generate_test_video(
        FIXTURES_DIR / "invalid_no_audio.mp4",
        duration=10,
        resolution="1920x1080",
        fps=60,
        codec="libx264",
        with_audio=False,
    )

    # Wrong FPS (24 FPS - not in ALLOWED_FPS)
    generate_test_video(
        FIXTURES_DIR / "invalid_wrong_fps_24.mp4",
        duration=10,
        resolution="1920x1080",
        fps=24,
        codec="libx264",
    )

    # Wrong FPS (30 FPS - not in ALLOWED_FPS for 1080p60 target)
    generate_test_video(
        FIXTURES_DIR / "invalid_wrong_fps_30.mp4",
        duration=10,
        resolution="1920x1080",
        fps=30,
        codec="libx264",
    )

    # Wrong resolution (1280x720 for 1920x1080 target)
    generate_test_video(
        FIXTURES_DIR / "invalid_wrong_resolution_720p.mp4",
        duration=10,
        resolution="1280x720",
        fps=60,
        codec="libx264",
    )

    # Wrong resolution (3840x2160 4K for 1920x1080 target)
    generate_test_video(
        FIXTURES_DIR / "invalid_wrong_resolution_4k.mp4",
        duration=10,
        resolution="3840x2160",
        fps=60,
        codec="libx264",
    )

    # Wrong codec (MPEG-4)
    generate_test_video(
        FIXTURES_DIR / "invalid_wrong_codec_mpeg4.mp4",
        duration=10,
        resolution="1920x1080",
        fps=60,
        codec="mpeg4",
    )

    # Wrong pixel format (yuv422p)
    generate_test_video(
        FIXTURES_DIR / "invalid_wrong_pixfmt.mp4",
        duration=10,
        resolution="1920x1080",
        fps=60,
        codec="libx264",
        pixel_format="yuv422p",
    )


def create_edge_case_videos() -> None:
    """Create edge case videos for boundary testing."""
    print("\n[INFO] Edge case videolari oluşturuluyor...")

    # Very short video (< 1 second)
    generate_test_video(
        FIXTURES_DIR / "edge_very_short_0.5s.mp4",
        duration=0.5,
        resolution="1920x1080",
        fps=60,
        codec="libx264",
    )

    # Exactly 1 second video
    generate_test_video(
        FIXTURES_DIR / "edge_exactly_1s.mp4",
        duration=1,
        resolution="1920x1080",
        fps=60,
        codec="libx264",
    )

    # 10 minute video (medium duration)
    generate_test_video(
        FIXTURES_DIR / "edge_10min.mp4",
        duration=600,
        resolution="1920x1080",
        fps=60,
        codec="libx264",
    )


def create_corrupted_files() -> None:
    """Create intentionally corrupted files for error handling tests."""
    print("\n[INFO] Bozuk dosyalar oluşturuluyor...")

    # Empty file
    (FIXTURES_DIR / "corrupted_empty.mp4").write_bytes(b"")

    # Invalid MP4 header
    (FIXTURES_DIR / "corrupted_invalid_header.mp4").write_bytes(b"INVALID_MP4_HEADER_DATA")

    # Text file pretending to be MP4
    (FIXTURES_DIR / "corrupted_text_file.mp4").write_text(
        "This is not a video file, just plain text."
    )

    # Partial/truncated MP4 (create valid video then truncate it)
    temp_video = FIXTURES_DIR / "temp_for_truncate.mp4"
    if generate_test_video(
        temp_video,
        duration=10,
        resolution="1920x1080",
        fps=60,
        codec="libx264",
    ):
        # Truncate to 1KB
        data = temp_video.read_bytes()
        truncated = data[:1024]
        (FIXTURES_DIR / "corrupted_truncated.mp4").write_bytes(truncated)
        temp_video.unlink()

    print("  [OK] Bozuk dosyalar oluşturuldu")


def create_test_audios() -> None:
    """Create test audio files for audio processing tests."""
    print("\n[INFO] Test ses dosyalari oluşturuluyor...")

    # Generate test audio files using FFmpeg
    audio_files = [
        ("test_audio_440hz.mp3", 440, 10),  # A4 note
        ("test_audio_880hz.mp3", 880, 10),  # A5 note
        ("test_audio_silence.mp3", 0, 10),  # Silence (using anullsrc)
        ("test_audio_stereo.mp3", 440, 10),  # Stereo test
    ]

    for filename, freq, duration in audio_files:
        output_path = FIXTURES_DIR / filename

        if freq == 0:
            # Silence
            src = f"anullsrc=r=48000:cl=stereo"
        else:
            # Sine wave
            src = f"sine=frequency={freq}:sample_rate=48000:duration={duration}"

        cmd = [
            "ffmpeg",
            "-y",
            "-f", "lavfi",
            "-i", src,
            "-c:a", "libmp3lame",
            "-b:a", "192k",
            str(output_path),
        ]

        try:
            subprocess.run(cmd, capture_output=True, check=True, timeout=30)
            print(f"  [OK] {filename}")
        except Exception as e:
            print(f"  [FAILED] {filename}: {e}")


def create_intro_loop_pairs() -> None:
    """Create matching intro/loop pairs for batch testing."""
    print("\n[INFO] Intro/loop ciftleri oluşturuluyor...")

    # Create multiple intro/loop pairs
    pairs = [
        ("test1_intro.mp4", "test1_loop.mp4"),
        ("lofi_intro.mp4", "lofi_loop.mp4"),
        ("ambient_intro.mp4", "ambient_loop.mp4"),
    ]

    for intro_name, loop_name in pairs:
        # Intro video (shorter, 5 seconds)
        generate_test_video(
            FIXTURES_DIR / intro_name,
            duration=5,
            resolution="1920x1080",
            fps=60,
            codec="libx264",
        )

        # Loop video (standard, 10 seconds)
        generate_test_video(
            FIXTURES_DIR / loop_name,
            duration=10,
            resolution="1920x1080",
            fps=60,
            codec="libx264",
        )


def generate_all_tests() -> None:
    """Generate all test fixtures."""
    print("=" * 60)
    print("AutoVideo Test Video Fixture Generator")
    print("=" * 60)

    if not check_ffmpeg():
        sys.exit(1)

    # Create fixtures directory
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n[INFO] Hedef dizin: {FIXTURES_DIR}")

    # Generate all test categories
    create_valid_videos()
    create_invalid_videos()
    create_edge_case_videos()
    create_corrupted_files()
    create_test_audios()
    create_intro_loop_pairs()

    # Summary
    print("\n" + "=" * 60)
    print("[COMPLETE] Test fixture'leri oluşturuldu!")
    print("=" * 60)

    # List generated files
    files = list(FIXTURES_DIR.glob("*"))
    print(f"\nToplam dosya sayisi: {len(files)}")
    print("\nOluşturulan dosyalar:")
    for f in sorted(files):
        size_mb = f.stat().st_size / (1024 * 1024) if f.is_file() else 0
        print(f"  - {f.name:40} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    generate_all_tests()
