#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video Renderer - Intro+Loop video birleştirme ve ses miksajı.

Kullanım:
    cd render/
    python3 render.py

Veya modül olarak:
    python3 -m video_renderer
"""

import sys
from pathlib import Path

# Add the script's directory to Python path for module discovery
sys.path.insert(0, str(Path(__file__).resolve().parent))

from video_renderer.main import main

if __name__ == "__main__":
    raise SystemExit(main())
