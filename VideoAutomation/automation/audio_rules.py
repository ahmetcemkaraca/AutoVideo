#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deterministic audio selection rules for themed video generation.
"""

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Dict, Iterable, List, Optional


THEME_RULES: Dict[str, Dict[str, object]] = {
    "jazz": {"music_db": -6.0, "bg": "ambient"},
    "medieval": {"music_db": None, "bg": "ambient"},
    "lofi": {"music_db": None, "bg": "432hz"},
}


@dataclass(frozen=True)
class AudioSelection:
    """Resolved audio selection for a render."""

    theme: Optional[str]
    music_db: Optional[float]
    background_profile: Optional[str]
    background_files: List[Path] = field(default_factory=list)
    visual_inspection_enabled: bool = False


def parse_background_gain_db(path: Path) -> Optional[float]:
    """Parse background gain from a filename like `bg_-8.5.mp3`."""

    stem = path.stem.lower()
    if "bg" not in stem:
        return None

    match = re.search(r"(?:^|[_-])bg[_-]?([+-]?\d+(?:\.\d+)?)", stem, re.IGNORECASE)
    if not match:
        return 0.0
    return float(match.group(1))


def is_background_audio(path: Path) -> bool:
    """Return True for audio files that are explicitly tagged as background."""

    stem = path.stem.lower()
    return stem.startswith("bg") or "_bg_" in stem


def select_theme_rule(theme: Optional[str]) -> Dict[str, object]:
    """Return the configured rule for a theme, falling back to no overrides."""

    if not theme:
        return {"theme": None, "music_db": None, "bg": None}

    rule = THEME_RULES.get(theme.lower())
    if rule is None:
        return {"theme": theme, "music_db": None, "bg": None}

    return {"theme": theme.lower(), **rule}


def select_audio_for_theme(
    tracks: Iterable[Path],
    theme: Optional[str] = None,
    visual_inspection_enabled: bool = False,
) -> AudioSelection:
    """Select background audio files and theme defaults without overwriting manual choice."""

    track_list = list(tracks)
    backgrounds = [track for track in track_list if is_background_audio(track)]
    rule = select_theme_rule(theme)
    music_db = rule.get("music_db")
    background_profile = rule.get("bg")

    if backgrounds:
        resolved_music_db = None
        for candidate in backgrounds:
            parsed = parse_background_gain_db(candidate)
            if parsed is not None:
                resolved_music_db = parsed
                break
        if resolved_music_db is None:
            resolved_music_db = music_db if isinstance(music_db, (int, float)) else None
        music_db = resolved_music_db if resolved_music_db is not None else music_db

    return AudioSelection(
        theme=rule.get("theme"),
        music_db=music_db if isinstance(music_db, (int, float)) else None,
        background_profile=background_profile if isinstance(background_profile, str) else None,
        background_files=backgrounds,
        visual_inspection_enabled=visual_inspection_enabled,
    )

