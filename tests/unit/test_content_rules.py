#!/usr/bin/env python3

from pathlib import Path

from video_renderer.content_rules import (
    ContentRulesEngine,
    detect_theme_from_name,
    is_background_sound,
    select_theme_music,
)


def test_detect_theme_from_filename():
    assert detect_theme_from_name(Path("intro_jazz.mp4"), Path("loop.mp4")) == "jazz"
    assert detect_theme_from_name(Path("intro.mp4"), Path("medieval_loop.mp4")) == "medieval"
    assert detect_theme_from_name(Path("intro.mp4"), Path("loop.mp4")) is None


def test_background_sound_detection():
    assert is_background_sound(Path("bg_rain.mp3"))
    assert is_background_sound(Path("fx_bg_wind.wav"))
    assert not is_background_sound(Path("music_theme.mp3"))


def test_select_theme_music(tmp_path):
    music_root = tmp_path / "music"
    jazz_dir = music_root / "jazz"
    jazz_dir.mkdir(parents=True)
    track = jazz_dir / "a_track.mp3"
    track.write_text("stub")
    assert select_theme_music(music_root, "jazz") == track


def test_engine_analyze_returns_expected_plan(tmp_path):
    music_root = tmp_path / "music"
    lofi_dir = music_root / "lofi"
    lofi_dir.mkdir(parents=True)
    expected = lofi_dir / "lofi_loop.mp3"
    expected.write_text("stub")

    engine = ContentRulesEngine(music_root=music_root)
    result = engine.analyze(Path("intro_lofi.mp4"), Path("loop_bg_rain.mp4"))

    assert result.theme == "lofi"
    assert result.music_path == expected
    assert result.background_paths == [Path("loop_bg_rain.mp4")]
    assert result.music_volume_db is None
    assert 8 * 3600 <= result.duration_seconds <= 10 * 3600
