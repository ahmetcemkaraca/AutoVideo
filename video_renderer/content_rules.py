#!/usr/bin/env python3
"""
Content rules for themed video rendering.

The rules are intentionally filename-first so batch rendering can run without
visual analysis in the MVP path. Visual inspection remains an optional future
extension.
"""

from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

THEMES = ("jazz", "medieval", "lofi")


@dataclass(frozen=True)
class ContentRulesResult:
    """Resolved content rules for a render pair."""

    theme: str | None
    music_path: Path | None
    background_paths: list[Path] = field(default_factory=list)
    music_volume_db: float | None = None
    duration_seconds: int = 0


def _normalize_name(path: Path) -> str:
    return path.stem.lower()


def detect_theme_from_name(*paths: Path) -> str | None:
    """Detect a theme from intro/loop filenames."""
    for path in paths:
        name = _normalize_name(path)
        for theme in THEMES:
            if theme in name:
                return theme
    return None


def is_background_sound(path: Path) -> bool:
    """Return True when the filename clearly marks a background sound."""
    name = _normalize_name(path)
    return name.startswith("bg") or "_bg_" in name


def select_theme_music(music_root: Path, theme: str) -> Path | None:
    """Pick the first music file from a theme-specific subdirectory."""
    theme_dir = music_root / theme
    if not theme_dir.exists():
        return None

    candidates = sorted(
        p
        for p in theme_dir.iterdir()
        if p.is_file() and p.suffix.lower() in {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
    )
    return candidates[0] if candidates else None


def collect_background_sounds(paths: Iterable[Path]) -> list[Path]:
    """Collect explicitly tagged background sounds."""
    return [path for path in paths if is_background_sound(path)]


def _music_volume_for_theme(theme: str | None) -> float | None:
    if theme == "jazz":
        return -6.0
    return None


def random_duration_seconds(min_hours: int = 8, max_hours: int = 10) -> int:
    """Return a random duration between 8 and 10 hours by default."""
    return random.randint(min_hours * 3600, max_hours * 3600)


class ContentRulesEngine:
    """Resolve themed music and background selection for a render job."""

    def __init__(self, music_root: Path | None = None, allow_visual_fallback: bool = False):
        self.music_root = music_root
        self.allow_visual_fallback = allow_visual_fallback

    def analyze(self, intro_path: Path, loop_path: Path) -> ContentRulesResult:
        """Analyze file names and resolve a content plan."""
        theme = detect_theme_from_name(intro_path, loop_path)
        music_path = None
        if theme and self.music_root is not None:
            music_path = select_theme_music(self.music_root, theme)

        background_paths = collect_background_sounds([intro_path, loop_path])
        if self.music_root is not None and self.music_root.exists():
            background_paths.extend(
                path
                for path in sorted(self.music_root.rglob("*"))
                if path.is_file() and is_background_sound(path) and path not in background_paths
            )

        return ContentRulesResult(
            theme=theme,
            music_path=music_path,
            background_paths=background_paths,
            music_volume_db=_music_volume_for_theme(theme),
            duration_seconds=random_duration_seconds(),
        )
