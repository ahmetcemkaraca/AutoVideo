# AutoVideo - Video Rendering & Automation System

[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Advanced video rendering and automation system that combines intro + loop videos into long-duration videos (8-10 hours) with automated audio processing, batch rendering, and cloud integration.

## Features

- **Batch Rendering**: Queue multiple render jobs with distinct configurations
- **Multi-Selection**: Select multiple videos in the TUI (Space key) to batch add them instantly
- **Smart Batch**: Automatically detect `*_intro.mp4` and `*_loop.mp4` pairs
- **Background Upload**: Automatically upload rendered videos to Google Drive while processing the next job
- **Smart Resolution**: Basic Mode automatically detects and preserves source resolution when possible
- **Duration Options**: Fixed presets, Custom HH:MM:SS, or Random (8-10 hours)
- **Format Support**: AV1, H.264, H.265/HEVC encoding with hardware acceleration support
- **Live TUI**: Rich Terminal User Interface built with Textual
- **YouTube Integration**: Automated YouTube upload with metadata management
- **Livestream Support**: Automated playlist generation for YouTube livestreams

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Components](#components)
- [Configuration](#configuration)
- [Architecture](#architecture)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

## Installation

### Prerequisites

- Python 3.10 or higher
- FFmpeg installed and available in PATH
- (Optional) Google Drive account for cloud uploads
- (Optional) YouTube account for automated uploads

### Step 1: Clone the Repository

```bash
git clone https://github.com/ahmetcemkaraca/AutoVideo
cd AutoVideo
```

### Step 2: Install Dependencies
şş
```bash
# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install in development mode (optional)
pip install -e .
```

### Step 3: Verify FFmpeg Installation

```bash
ffmpeg -version
ffprobe -version
```

If FFmpeg is not installed, install it:

- **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH
- **macOS**: `brew install ffmpeg`
- **Linux**: `sudo apt install ffmpeg` or `sudo yum install ffmpeg`

### Step 4: Google Drive Setup (Optional)

1. Place your `client_secrets.json` file in the project root
2. First time you upload, a browser window will open to authenticate
3. Grant necessary permissions for Google Drive access

## Quick Start

### Interactive TUI Mode (Recommended)

```bash
python -m video_renderer --tui
```

The TUI provides:
- **Batch**: Manage queue, add jobs, view progress
- **Settings**: Configure rendering options, enable Drive upload
- **Smart Batch**: Auto-detect video pairs in the working directory

### CLI Mode

```bash
# Interactive wizard
python -m video_renderer

# Smart Batch mode (auto-detects pairs)
python -m video_renderer --batch

# Resume from interrupted session
python -m video_renderer --resume

# List available hardware encoders
python -m video_renderer --list-hw
```

## Usage

### Main Video Renderer

#### Single Video Rendering

```bash
python -m video_renderer
```

Follow the interactive wizard to:
1. Select intro and loop videos
2. Choose audio tracks
3. Configure duration and codec
4. Start rendering

#### Batch Rendering

```bash
python -m video_renderer --tui
```

In the TUI:
1. Navigate to **Batch** screen
2. Select multiple videos with **Space** key
3. Configure batch settings
4. Queue multiple jobs
5. Monitor progress in real-time

#### Smart Batch Mode

```bash
python -m video_renderer --batch
```

Automatically detects and queues all `*_intro.mp4` / `*_loop.mp4` pairs in the current directory.

### VideoAutomation Pipeline

The VideoAutomation component provides end-to-end automation with YouTube upload.

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

Automated playlist generation for YouTube livestreams.

```bash
cd VideoLivestream

# Initialize configuration
python run_livestream.py --init

# Generate playlists for all video sets
python run_livestream.py --generate

# Start livestream
python run_livestream.py
```

## Components

### video_renderer/

Main video rendering package with TUI interface.

- **app.py**: VideoRendererApp - main TUI application
- **main.py**: CLI entry point with wizard
- **ffmpeg.py**: FFmpeg command execution with progress parsing
- **video.py**: VideoEncoder - encoding, normalization, concatenation
- **audio.py**: AudioProcessor - looping, mixing, validation
- **config.py**: Codec configs, hardware encoder detection
- **batch.py**: BatchQueue, RenderJob, SmartBatchDetector
- **drive.py**: Google Drive upload integration
- **screens/**: TUI screens (Home, Batch, Settings, Render, Complete, SmartBatch)

### VideoAutomation/

Automated pipeline with YouTube upload.

- **run_automation.py**: CLI entry point
- **automation/pipeline.py**: End-to-end automation orchestrator
- **automation/youtube.py**: YouTube upload automation
- **automation/config.py**: Configuration management
- **automation/state.py**: State persistence

### VideoLivestream/

YouTube livestream automation.

- **run_livestream.py**: CLI entry point
- **livestream/scheduler.py**: Stream scheduling
- **livestream/mixer.py**: Content mixing
- **livestream/streamer.py**: Stream management

### video_renderer_ramtest/

Testing variant with optional core logic sharing.

- **app.py**: Test TUI with "Use Main Renderer" toggle
- Mirrors main renderer structure with testing controls

## Configuration

### File Structure Conventions

**Main Renderer**:
- **Input Videos**: Working directory (`.mp4`, `.mkv`, `.mov`, etc.)
- **Music**: `music/` or `Music/` directory
- **Background Audio**: `background/` directory or files with `bg` prefix
- **Temporary Files**: `tmp/` directory
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

### Codec Configuration

The system supports multiple codecs with automatic hardware acceleration detection:

**Priority Order**:
1. NVENC (NVIDIA): `h264_nvenc`, `hevc_nvenc`, `av1_nvenc`
2. QSV (Intel): `h264_qsv`, `hevc_qsv`
3. VAAPI (AMD/Intel Linux): `h264_vaapi`, `hevc_vaapi`
4. Software: `libx264`, `libx265`, `libsvtav1`

### Audio Background Detection

Files starting with `bg` or containing `_bg_` are treated as background audio. Gain values parsed from filenames (e.g., `bg_-8.5.mp3` → -8.5 dB).

## Architecture

### Data Flow

**Render Pipeline**:
```
Video Path:  Intro → Normalize → Loop → Normalize → Concat (to target duration)
Audio Path:  Tracks → Validate → Loop → Mix with backgrounds → Final audio
Final:       Video + Audio → Mux → Final output
```

**Parallel Execution**: Video encoding and audio processing run concurrently using `ThreadPoolExecutor`.

### TUI State Management

`VideoRendererApp` class holds global application state:
- `queue`: Shared `BatchQueue` instance for managing jobs
- `drive_folder_id`, `enable_upload`: Drive integration settings
- `render_mode`: Tracks Single, Intro/Loop, or Batch mode

### Batch System

Thread-safe `BatchQueue` manages `RenderJob` objects with:
- Persistence to `tmp/batch_queue.json`
- Callbacks for progress, completion, and errors
- Background thread processing with UI updates

### Smart Batch Detection

`SmartBatchDetector.scan()` uses regex patterns to find matching intro/loop pairs:
- Patterns: `{name}_intro.mp4` / `{name}_loop.mp4`
- Variations: `_intro`, `-intro`, `intro` (case-insensitive)

## Troubleshooting

### FFmpeg Not Found

```bash
# Check if FFmpeg is in PATH
ffmpeg -version

# If not found, install FFmpeg:
# Windows: Download from ffmpeg.org and add to PATH
# macOS: brew install ffmpeg
# Linux: sudo apt install ffmpeg
```

### Hardware Acceleration Not Working

```bash
# List available hardware encoders
python -m video_renderer --list-hw

# Check if your GPU is detected
# NVIDIA: nvidia-smi
# Intel: vainfo (Linux)
```

### Audio Validation Errors

- Ensure audio files are in MP3, WAV, or FLAC format
- Check that files are not corrupted
- Verify file paths are correct

### Google Drive Authentication Failed

- Ensure `client_secrets.json` is in the project root
- Check your Google Cloud Console settings
- Verify OAuth consent screen is configured

### TUI Rendering Issues

- Ensure terminal supports UTF-8
- Try increasing terminal window size
- Check for Color Profile compatibility (use True Color if available)

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/AutoVideo
cd AutoVideo

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install in development mode
pip install -e .

# Run tests (if available)
pytest tests/
```

### Code Style

- Follow PEP 8 guidelines
- Use type hints where appropriate
- Add docstrings to functions and classes
- Keep functions focused and modular

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- **Textual**: For the excellent TUI framework
- **FFmpeg**: For the powerful multimedia processing
- **Rich**: For beautiful terminal output

## Support

- **Documentation**: See [docs/](docs/) for detailed guides
- **Issues**: Report bugs on [GitHub Issues](https://github.com/ahmetcemkaraca/AutoVideo/issues)
- **Discussions**: Join our [GitHub Discussions](https://github.com/ahmetcemkaraca/AutoVideo/discussions)

## Roadmap

- [ ] Web-based UI
- [ ] Docker containerization
- [ ] More codec support
- [ ] Plugin system
- [ ] Distributed rendering
- [ ] Cloud rendering support

---

**AutoVideo** - Automating video creation with Python and FFmpeg.
