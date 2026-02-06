# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AutoVideo is a Python-based video rendering and automation system that:
- Combines intro + loop videos into long-duration videos (8-10 hours)
- Processes and mixes audio tracks with background sounds
- Provides both TUI (Textual) and CLI interfaces
- Supports batch rendering with auto-detection of intro/loop pairs
- Integrates with Google Drive and YouTube for automatic uploads

## Commands

### Installation & Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .

# Verify FFmpeg installation
ffmpeg -version
ffprobe -version
```

### Running the Application
```bash
# Interactive TUI mode (recommended)
python -m video_renderer --tui

# Interactive CLI wizard
python -m video_renderer

# Smart Batch mode (auto-detects *_intro.mp4 / *_loop.mp4 pairs)
python -m video_renderer --batch

# Resume from interrupted session
python -m video_renderer --resume

# List available hardware encoders
python -m video_renderer --list-hw
```

### VideoAutomation Pipeline
```bash
cd VideoAutomation

# Initialize configuration
python run_automation.py --init

# Add your music files to music/ directory (MP3, WAV, FLAC)

# Authenticate YouTube (first time only)
python run_automation.py --auth-youtube

# Generate single video
python run_automation.py --config config.json

# Continuous mode (infinite loop)
python run_automation.py --config config.json --continuous

# View statistics
python run_automation.py --stats
```

### VideoLivestream Pipeline
```bash
cd VideoLivestream

# Initialize configuration
python run_livestream.py --init

# Generate playlists for all video sets
python run_livestream.py --generate

# Start livestream
python run_livestream.py
```

## Architecture

### Project Structure

The project consists of multiple integrated components:

```
├── video_renderer/           # Main video rendering package
│   ├── screens/              # TUI screens (Home, Batch, Settings, etc.)
│   ├── app.py               # VideoRendererApp - main TUI application
│   ├── main.py              # CLI entry point with wizard
│   ├── ffmpeg.py            # FFmpeg command execution, progress parsing
│   ├── video.py             # VideoEncoder - encoding, normalization, concat
│   ├── audio.py             # AudioProcessor - looping, mixing, validation
│   ├── config.py            # Codec configs, hardware encoder detection
│   ├── batch.py             # BatchQueue, RenderJob, SmartBatchDetector
│   ├── drive.py             # Google Drive upload integration
│   └── tui.py               # CLI utilities (Rich console, tables, progress)
│
├── video_renderer_ramtest/   # Testing variant with optional core logic sharing
│   └── screens/              # Mirrors main renderer with testing controls
│
├── VideoAutomation/          # Automated pipeline with YouTube upload
│   ├── automation/           # Pipeline modules
│   │   ├── youtube.py       # YouTube upload automation
│   │   ├── pipeline.py      # End-to-end automation orchestrator
│   │   ├── config.py        # Configuration management
│   │   └── state.py         # State persistence
│   ├── run_automation.py    # CLI entry point
│   └── video_renderer/       # Shared rendering core
│
├── VideoLivestream/          # YouTube livestream automation
│   ├── livestream/           # Stream scheduling and mixing
│   ├── run_livestream.py    # CLI entry point
│   └── content/              # Video sets (set1_ambient/, set2_lofi/, etc.)
│
├── tmp/                      # Temporary files (intermediate encoded, concat lists)
└── archive/                  # Post-render source file management
```

### Core Modules

**`video_renderer/`** - Main package containing:
- **`app.py`** - Textual TUI application (`VideoRendererApp`) with screen management
- **`main.py`** - CLI entry point with interactive wizard and batch processing
- **`ffmpeg.py`** - FFmpeg command execution with progress parsing (`FFmpegRunner`, `probe_video`)
- **`video.py`** - Video encoding, normalization, concatenation (`VideoEncoder`)
- **`audio.py`** - Audio processing, looping, mixing (`AudioProcessor`)
- **`config.py`** - Codec configurations, hardware detection (`get_best_encoder`, `detect_available_encoders`)
- **`batch.py`** - Batch queue management (`BatchQueue`, `RenderJob`, `SmartBatchDetector`)
- **`drive.py`** - Google Drive upload integration (`DriveUploader`)
- **`screens/`** - TUI screens (Home, VideoSelect, AudioSelect, Settings, Render, Complete, Batch, SmartBatch)
- **`tui.py`** - CLI utilities for terminal output (Rich console, tables, progress bars)

### Data Flow

**Session Persistence** (`tmp/last_session.json`, `tmp/batch_queue.json`) - Stores render configuration and batch queue state for resume capability.

**Render Pipeline**:
```
Video Path:  Intro → Normalize → Loop → Normalize → Concat (to target duration)
Audio Path:  Tracks → Validate → Loop → Mix with backgrounds → Final audio
Final:       Video + Audio → Mux → Final output
```

**Parallel Execution**: Video encoding and audio processing run concurrently using `ThreadPoolExecutor`.

**TUI State Management**: `VideoRendererApp` class holds global application state:
- `queue`: Shared `BatchQueue` instance for managing jobs across screens
- `drive_folder_id`, `enable_upload`: Drive integration settings
- `render_mode`: Tracks Single, Intro/Loop, or Batch mode

### Key Patterns

**Codec Selection**: `get_best_encoder()` detects and prioritizes hardware encoders (NVENC, QSV, VAAPI) over software encoders.

**Compatibility Check**: `VideoEncoder.check_compatibility()` determines re-encoding needs by checking resolution, codec, FPS, and pixel format.

**Smart Resolution**: In Basic Mode, if intro and loop share the same resolution, it's preserved to avoid re-encoding loss.

**Batch Detection**: `SmartBatchDetector.scan()` uses regex patterns to find matching intro/loop pairs:
- Patterns: `{name}_intro.mp4` / `{name}_loop.mp4`
- Variations: `_intro`, `-intro`, `intro` (case-insensitive)

**Audio Background Detection**: Files starting with `bg` or containing `_bg_` are treated as background audio. Gain values parsed from filenames (e.g., `bg_-8.5.mp3` → -8.5 dB).

**Progress Tracking**: `FFmpegRunner` parses FFmpeg stderr for frame count, FPS, time, bitrate, and speed.

**Intermediate Files**:
- Video: MP4 containers
- Audio: W64 (Wave64) format for >4GB file support

**BatchQueue Thread-Safe Operations**: The `BatchQueue` manages `RenderJob` objects with:
- Persistence to `tmp/batch_queue.json`
- Callbacks for progress, completion, and errors
- Background thread processing with UI updates

### File Structure Conventions

**Main Renderer**:
- **Input Videos**: Working directory (`.mp4`, `.mkv`, `.mov`, etc.)
- **Music**: `music/` or `Music/` directory
- **Background Audio**: `background/` directory or files with `bg` prefix
- **Temporary Files**: `tmp/` directory (intermediate encoded files, concat lists, audio loops)
- **Output**: `final_<name>_<codec>_<duration>.mp4` in working directory
- **Archive**: `archive/<timestamp>/` for post-render source file management

**VideoAutomation**:
- **Config**: `config.json` (settings, styles, genres)
- **YouTube Auth**: `client_secrets.json`
- **Music**: `music/` (user-provided MP3/WAV/FLAC files)
- **Output**: `output/` (rendered videos)
- **State**: `state.json` (video records and statistics)

**VideoLivestream**:
- **Content Sets**: `content/set{N}_{name}/` (e.g., `set1_ambient/`)
- **Per Set**: `intro.mp4`, `loop.mp4`, `music/`, `bg/`, `playlists/`
- **Playlists**: 10 JSON files per set with different track orderings

## Important Notes

- **Python Version**: Requires Python 3.10+ (per pyproject.toml)
- **FFmpeg Required**: System must have `ffmpeg` and `ffprobe` installed and in PATH
- **Hardware Acceleration**: Automatically detected and used when available (NVENC, QSV, VAAPI)
- **Session Resume**: Interrupted renders can be resumed using `--resume` flag
- **Smart Batch**: Automatically detects intro/loop pairs using regex patterns
- **Audio Validation**: Tracks are validated before rendering; corrupted files are reported
- **File Cleanup**: TUI automatically cleans stale tmp files before starting new renders

## Ramtest Variant Integration

**`video_renderer_ramtest/`** is a testing variant designed for:
- Testing logic changes in isolated environment
- Running in memory-constrained environments
- Optionally loading core logic from main `video_renderer/` to verify consistency

**Key Difference**: The ramtest version includes a "Use Main Renderer" toggle in its TUI that allows switching between its own implementation and the shared core logic from `video_renderer/`.

## RenderJob Modes

The batch system supports two distinct rendering modes:

**`intro_loop` Mode**:
- Classic intro + loop concatenation
- Normalize both videos → Concat to target duration → Audio processing → Mux

**`single` Mode**:
- Single video processing (format conversion, audio replacement)
- Normalize/Encode → Audio processing → Mux (no concatenation step)
