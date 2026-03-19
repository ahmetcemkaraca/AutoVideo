#!/usr/bin/env python3
"""Check local render prerequisites for AutoVideo.

This script reports the most common setup blockers before starting a long render
run. It exits non-zero when a required dependency or directory is missing.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


REQUIRED_COMMANDS = ("ffmpeg", "ffprobe")
REQUIRED_DIRECTORIES = ("music",)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    problems: list[str] = []

    print("AutoVideo environment check")
    print(f"Repository root: {repo_root}")

    for command in REQUIRED_COMMANDS:
        resolved = shutil.which(command)
        if resolved:
            print(f"[OK] {command}: {resolved}")
        else:
            problems.append(f"Missing command: {command}")
            print(f"[MISSING] {command}")

    for directory in REQUIRED_DIRECTORIES:
        path = repo_root / directory
        if path.exists():
            print(f"[OK] {directory}/")
        else:
            problems.append(f"Missing directory: {directory}/")
            print(f"[MISSING] {directory}/")

    if problems:
        print("\nBlockers:")
        for problem in problems:
            print(f"- {problem}")
        print("\nInstall FFmpeg and create the missing directories before rendering.")
        return 1

    print("\nEnvironment looks ready for a render attempt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
