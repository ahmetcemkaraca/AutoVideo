# Ramtest vs Normal Module Comparison

This document outlines the technical and code differences between the production `video_renderer` module and the testing `video_renderer_ramtest` module.

## Purpose

- **video_renderer (Normal)**: The stable, production-ready version used for actual video processing tasks.
- **video_renderer_ramtest (Ramtest)**: A development/testing sandbox. It mirrors the structure of the main renderer but allows developers to test UI changes, experimental logic, or different configurations without affecting the stable build.

## Key Differences

### 1. Integration with Core Logic
- **Normal**: Tightly coupled with its own internal logic files (`video.py`, `ffmpeg.py`, `audio.py`).
- **Ramtest**: Features a hybrid approach. 
    - By default, it uses its own local copies of logic files.
    - **New**: It has a "Use Main Renderer" setting that dynamically imports the core logic code from the `video_renderer` package, effectively running the production engine under the test UI.

### 2. UI Differences (Settings Screen)
- **Normal**: Standard settings for codec, duration, and output configuration.
- **Ramtest**: Includes an additional "Test Options" section:
    - `[x] Video Renderer Paketini Kullan`: Testing toggle to switch backend implementations.

### 3. Code Structure & Dynamic Imports
The most significant code difference lies in `screens/render.py` and `screens/batch.py`.

**Normal (`video_renderer`):**
```python
from ..ffmpeg import FFmpegRunner, AudioProcessor
from ..video import VideoEncoder
```
static imports from local package.

**Ramtest (`video_renderer_ramtest`):**
```python
# Check app state
use_main = getattr(self.app, "use_main_renderer", False)

if use_main:
    # Dynamic import from separate production package
    from video_renderer.ffmpeg import FFmpegRunner
    from video_renderer.video import VideoEncoder
else:
    # Fallback to local copy
    from ..ffmpeg import FFmpegRunner
    from ..video import VideoEncoder
```

### 4. Independence
- `video_renderer` does not know about `ramtest`.
- `video_renderer_ramtest` may depend on `video_renderer` if the cross-module feature is used.

## Usage Strategy
- **Development**: Use `Ramtest` to build new screens or try new FFmpeg flags safely.
- **Production**: Use `Normal` for reliability.
- **Verification**: Use `Ramtest` with "Main Renderer" enabled to verify that UI changes in Ramtest work correctly with the production engine.

## Experimental Logic (Unimplemented in Production)

The `video_renderer_ramtest` module contains experimental configuration files and logic concepts that are **not** present in the main module and are currently **unused** (dead code) even in Ramtest, but serve as a blueprint for future optimizations.

### 1. Advanced Memory Management (`ram_config.py`)
Found only in `video_renderer_ramtest`, this file outlines:
- **RAM Disk Support**: Logic to use `/dev/shm` (Linux shared memory) for temporary file storage to reduce SSD wear and improve speed.
- **Chunked Processing**: Logic to split very long videos (12h+) into chunks for processing on systems with limited RAM.
- **GPU Tuning**: Aggressive `GPU_CONFIG` settings (128 surfaces, 48 rc-lookahead) optimized specifically for 20GB+ VRAM cards, whereas the main renderer uses safer, more compatible defaults.

## Version Divergence (As of Latest Update)

Since `video_renderer` (Normal) is the active development target, it currently has features that `video_renderer_ramtest`'s **local** logic lacks:

1. **Smart Batch Regex**: `video_renderer/batch.py` supports fuzzy matching (`*intro*.mp4`), while `ramtest`'s local `batch.py` still requires strict naming (`_intro.mp4`).
2. **Smart Resolution (CLI)**: The CLI Wizard (`video_renderer/main.py`) implements "Smart Resolution" in Basic Mode. The Ramtest local render logic (and even the Main TUI logic) currently defaults to fixed 1080p.

