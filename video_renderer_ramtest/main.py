#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compatibility shim for legacy video_renderer_ramtest entrypoint.

All execution is now routed to unified `video_renderer` with ramtest mode.
"""

from __future__ import annotations

import sys

from video_renderer.main import main as unified_main


def main() -> int:
    """Run unified renderer in ramtest mode unless user already picked a mode."""
    has_mode_flag = any(
        arg in {"--mode", "--rm", "--ramtest", "--ramdisk", "--high-vram"}
        for arg in sys.argv[1:]
    )

    if not has_mode_flag:
        sys.argv = [sys.argv[0], "--mode", "ramtest", *sys.argv[1:]]

    return unified_main()


if __name__ == "__main__":
    raise SystemExit(main())
