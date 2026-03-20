#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for deterministic audio selection rules."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from automation.audio_rules import (
    THEME_RULES,
    is_background_audio,
    parse_background_gain_db,
    select_audio_for_theme,
    select_theme_rule,
)


def test_theme_rules_include_expected_defaults():
    assert THEME_RULES["jazz"]["music_db"] == -6.0
    assert THEME_RULES["medieval"]["bg"] == "ambient"
    assert THEME_RULES["lofi"]["bg"] == "432hz"


def test_parse_background_gain_from_filename():
    assert parse_background_gain_db(Path("bg_-8.5.mp3")) == -8.5
    assert parse_background_gain_db(Path("intro.mp3")) is None


def test_background_audio_detection():
    assert is_background_audio(Path("bg_rain.mp3"))
    assert is_background_audio(Path("music_bg_ambient.wav"))
    assert not is_background_audio(Path("theme_song.mp3"))


def test_select_theme_rule_falls_back_for_unknown_theme():
    rule = select_theme_rule("unknown")
    assert rule["theme"] == "unknown"
    assert rule["music_db"] is None
    assert rule["bg"] is None


def test_select_audio_for_theme_prefers_filename_gain():
    selection = select_audio_for_theme(
        [Path("bg_-8.5.mp3"), Path("music.mp3")],
        theme="jazz",
    )
    assert selection.theme == "jazz"
    assert selection.music_db == -8.5
    assert selection.background_profile == "ambient"
    assert selection.background_files == [Path("bg_-8.5.mp3")]
