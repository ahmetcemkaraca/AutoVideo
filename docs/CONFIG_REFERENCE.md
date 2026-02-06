# Configuration Reference

Complete reference for AutoVideo v1.0.0 configuration options.

---

## Table of Contents

- [Render Modes](#render-modes)
- [Command-Line Options](#command-line-options)
- [Config File Format](#config-file-format)
- [Environment Variables](#environment-variables)
- [Codec Configuration](#codec-configuration)
- [GPU Configuration](#gpu-configuration)
- [Audio Configuration](#audio-configuration)
- [Batch Configuration](#batch-configuration)
- [Path Configuration](#path-configuration)

---

## Render Modes

AutoVideo v1.0.0 supports multiple render modes optimized for different hardware configurations.

### Standard Mode

Default mode with balanced performance and compatibility.

```bash
python -m video_renderer --tui --mode standard
```

**Characteristics:**
- Standard GPU buffers
- Disk-based temp files
- Balanced memory usage
- Best compatibility

**Use when:**
- General purpose rendering
- Unknown hardware capabilities
- Maximum compatibility needed

### Ramtest Mode

Memory-constrained system optimization with tracking.

```bash
python -m video_renderer --tui --mode ramtest
```

**Characteristics:**
- RAM disk for temp files (Linux)
- Memory usage tracking
- High VRAM optimization
- Rate limiting enabled

**Use when:**
- Limited system RAM
- Want memory profiling
- Testing memory constraints

**Requirements:**
- Linux tmpfs support (for RAM disk)
- At least 16GB system RAM
- GPU with 8GB+ VRAM

### Ramdisk Mode

High-performance mode using RAM disk without tracking.

```bash
python -m video_renderer --tui --mode ramdisk
```

**Characteristics:**
- RAM disk for temp files
- No memory tracking overhead
- Maximum I/O performance
- No rate limiting

**Use when:**
- Maximum performance needed
- Sufficient RAM available
- Don't need memory profiling

**Requirements:**
- Linux tmpfs or equivalent
- 32GB+ system RAM
- 10GB+ free RAM disk space

### High VRAM Mode

Optimized for GPUs with large VRAM.

```bash
python -m video_renderer --tui --mode high_vram
```

**Characteristics:**
- Increased GPU buffers (128 surfaces)
- Larger decode surfaces
- Extended lookahead
- Disk-based temp files

**Use when:**
- GPU with 20GB+ VRAM
- Maximum GPU utilization
- Long-duration renders

**GPU Buffer Settings:**
```python
gpu_surfaces: 128
gpu_extra_frames: 16
gpu_lookahead: 48
gpu_decode_surfaces: 32
```

---

## Command-Line Options

### Basic Options

```
--tui                      Launch Textual UI interface
--mode <mode>              Render mode (standard|ramtest|ramdisk|high_vram)
--batch                    Batch processing mode
--resume                   Resume interrupted session
--help                     Show help message
--version                  Show version information
```

### Hardware Options

```
--list-hw                  List available hardware encoders
--hw-accel                 Enable hardware acceleration
--no-hw-accel              Disable hardware acceleration
--refresh-cache            Refresh hardware detection cache
```

### Configuration Options

```
--config <path>            Use custom config file
--codec <codec>            Override codec (h264|h265|av1)
--preset <preset>          Override encoder preset
--crf <value>              Override CRF value
--duration <seconds>       Override target duration
```

### Debug Options

```
--verbose                  Enable verbose output
--debug                    Enable debug logging
--health-check             Run system health check
--validate-config          Validate configuration file
```

### Automation Options

```
--auth-youtube             Authenticate with YouTube
--auth-drive               Authenticate with Google Drive
--stats                    Show statistics
```

---

## Config File Format

### Default Config Location

- Linux: `~/.config/autovideo/config.json`
- Windows: `%APPDATA%\autovideo\config.json`
- macOS: `~/Library/Application Support/autovideo/config.json`

### Complete Config Schema

```json
{
    "version": "1.0.0",

    "encoder": {
        "default_codec": "h264",
        "preset": "fast",
        "crf": 20,
        "profile": "high",
        "level": "4.2"
    },

    "render_mode": "standard",

    "video": {
        "width": 1920,
        "height": 1080,
        "fps": 60,
        "colorspace": "bt709"
    },

    "audio": {
        "sample_rate": 48000,
        "bit_depth": 16,
        "channels": "auto",
        "normalize": true
    },

    "gpu": {
        "surfaces": 64,
        "extra_frames": 8,
        "lookahead": 32,
        "decode_surfaces": 16
    },

    "paths": {
        "tmp_dir": "tmp",
        "music_dir": "music",
        "background_dir": "background",
        "output_dir": "."
    },

    "batch": {
        "max_concurrent": 1,
        "auto_detect": true,
        "patterns": ["_intro", "-intro", "intro"]
    },

    "upload": {
        "enable_drive": false,
        "enable_youtube": false,
        "drive_folder_id": null
    },

    "security": {
        "encrypt_credentials": true,
        "validate_permissions": true,
        "audit_log": true
    }
}
```

### Encoder Section

```json
{
    "encoder": {
        "default_codec": "h264|h265|av1",
        "preset": "fast|medium|slow",
        "crf": 0-51,
        "profile": "baseline|main|high",
        "level": "3.0|4.0|4.2|5.0|5.1"
    }
}
```

**Codec Options:**

| Codec | Description | Quality | Speed | Compatibility |
|-------|-------------|---------|-------|---------------|
| h264 | H.264/AVC | Good | Fast | Excellent |
| h265 | H.265/HEVC | Better | Medium | Good |
| av1 | AV1 | Best | Slow | Growing |

**Preset Options:**

| Preset | Quality | Speed | Use Case |
|--------|---------|-------|----------|
| fast | Good | Fast | Quick renders |
| medium | Better | Medium | Balance |
| slow | Best | Slow | Final output |

**CRF Values:**

- **0-23**: Near-lossless to high quality
- **23-28**: Good quality (recommended)
- **28-35**: Medium quality
- **35-51**: Low quality

---

## Environment Variables

### Render Configuration

```bash
# Render mode
export AUTORENDER_MODE=standard
export AUTORENDER_MODE=ramtest
export AUTORENDER_MODE=ramdisk
export AUTORENDER_MODE=high_vram

# Hardware acceleration
export AUTORENDER_HW_ACCEL=true
export AUTORENDER_HW_ACCEL=false

# RAM disk
export AUTORENDER_RAM_DISK=true
export AUTORENDER_RAM_DISK=false

# High VRAM
export AUTORENDER_HIGH_VRAM=true
export AUTORENDER_HIGH_VRAM=false
```

### Path Configuration

```bash
# Temporary directory
export AUTORENDER_TMP_DIR=/tmp/autovideo

# Music directory
export AUTORENDER_MUSIC_DIR=~/Music

# Background audio directory
export AUTORENDER_BG_DIR=~/Backgrounds

# Output directory
export AUTORENDER_OUTPUT_DIR=~/Videos
```

### Encoder Configuration

```bash
# Default codec
export AUTORENDER_CODEC=h264

# Encoder preset
export AUTORENDER_PRESET=fast

# CRF value
export AUTORENDER_CRF=20

# Hardware encoder preference
export AUTORENDER_HW_PREFERENCE=nvenc|qsv|vaapi
```

### Batch Configuration

```bash
# Max concurrent jobs
export AUTORENDER_MAX_CONCURRENT=1

# Auto-detect pairs
export AUTORENDER_AUTO_DETECT=true

# Enable rate limiting
export AUTORENDER_RATE_LIMIT=true
```

### Upload Configuration

```bash
# Enable Google Drive
export AUTORENDER_ENABLE_DRIVE=true

# Enable YouTube
export AUTORENDER_ENABLE_YOUTUBE=true

# Drive folder ID
export AUTORENDER_DRIVE_FOLDER_ID=<folder-id>
```

### Security Configuration

```bash
# Encrypt credentials
export AUTORENDER_ENCRYPT_CREDS=true

# Validate permissions
export AUTORENDER_VALIDATE_PERMS=true

# Enable audit logging
export AUTORENDER_AUDIT_LOG=true

# Credential file path
export AUTORENDER_CREDS_PATH=~/.config/autovideo/credentials.json
```

### Debug Configuration

```bash
# Log level
export AUTORENDER_LOG_LEVEL=DEBUG|INFO|WARNING|ERROR

# Log file
export AUTORENDER_LOG_FILE=/var/log/autovideo/app.log

# Enable profiling
export AUTORENDER_PROFILE=false

# Memory tracking
export AUTORENDER_TRACK_MEMORY=false
```

---

## Codec Configuration

### H.264

**Best for:** Maximum compatibility

```python
from video_renderer.config import CODEC_H264

codec = CODEC_H264
# name: "H.264"
# encoder: "libx264"
# preset: "fast"
# crf: 20
# profile: "high"
# level: "4.2"
```

**Hardware variants:**
- `CODEC_H264_NVENC` - NVIDIA NVENC
- `CODEC_H264_QSV` - Intel Quick Sync
- `CODEC_H264_VAAPI` - VAAPI (Linux)

### H.265

**Best for:** Better compression

```python
from video_renderer.config import CODEC_H265

codec = CODEC_H265
# name: "H.265"
# encoder: "libx265"
# preset: "fast"
# crf: 23
```

**Hardware variants:**
- `CODEC_H265_NVENC` - NVIDIA NVENC
- `CODEC_H265_QSV` - Intel Quick Sync
- `CODEC_H265_VAAPI` - VAAPI (Linux)

### AV1

**Best for:** Best compression

```python
from video_renderer.config import CODEC_AV1

codec = CODEC_AV1
# name: "AV1"
# encoder: "libsvtav1"
# preset: "6"
# crf: 28
```

**Hardware variants:**
- `CODEC_AV1_NVENC` - NVIDIA NVENC (RTX 40-series+)

---

## GPU Configuration

### NVIDIA NVENC

**Supported GPUs:** Most NVIDIA GPUs (GTX 10-series+)

**Optimization levels:**

| Profile | Surfaces | Extra Frames | VRAM Required |
|---------|----------|--------------|---------------|
| standard | 64 | 8 | 4GB+ |
| high_vram | 128 | 16 | 8GB+ |
| ultra | 192 | 24 | 12GB+ |

**Configuration:**
```python
from video_renderer.config import get_render_config

config = get_render_config("high_vram")
# gpu_surfaces: 128
# gpu_extra_frames: 16
# gpu_lookahead: 48
# gpu_decode_surfaces: 32
```

### Intel QSV

**Supported CPUs:** Intel CPUs with Quick Sync (4th Gen+)

**Configuration:**
```python
# QSV uses fixed settings
# No additional configuration needed
```

### VAAPI

**Supported GPUs:** AMD and Intel GPUs on Linux

**Device detection:** Automatic

**Configuration:**
```python
# VAAPI uses default settings
# Device path: /dev/dri/renderD128 (auto-detected)
```

---

## Audio Configuration

### Supported Formats

- **Input:** MP3, WAV, FLAC, OGG, M4A, AAC, WMA
- **Output:** W64 (Wave64 for >4GB support)

### Sample Rate

```python
# Default: 48000 Hz
# Options: 44100, 48000, 96000

sample_rate = 48000
```

### Bit Depth

```python
# Default: 16-bit
# Options: 16, 24, 32

bit_depth = 16
```

### Channels

```python
# Default: auto-detect
# Options: 1 (mono), 2 (stereo), auto

channels = "auto"
```

### Background Audio

**Gain detection from filename:**
- `bg_-8.mp3` → -8 dB
- `background_-12.5.mp3` → -12.5 dB
- `bg_something.mp3` → 0 dB (default)

**Manual gain:**
```python
backgrounds = [
    (Path("bg1.mp3"), -8.5),  # -8.5 dB
    (Path("bg2.mp3"), -12.0), # -12 dB
]
```

---

## Batch Configuration

### Auto-Detection Patterns

Default patterns for intro/loop pair detection:

```python
patterns = [
    "_intro",  # video_intro.mp4 / video_loop.mp4
    "-intro",  # video-intro.mp4 / video-loop.mp4
    "intro",   # videoIntro.mp4 / videoLoop.mp4
]
```

**Custom patterns:**
```json
{
    "batch": {
        "auto_detect": true,
        "patterns": ["_start", "_begin", "intro"]
    }
}
```

### Concurrent Jobs

```python
# Max concurrent render jobs
max_concurrent = 1  # Default: 1

# For systems with high VRAM:
max_concurrent = 2  # RTX 3080+ or equivalent
```

### Rate Limiting

```python
# Enable rate limiting for memory management
enable_rate_limiting = True  # Default in ramtest mode
```

---

## Path Configuration

### Directory Structure

```
project/
├── music/              # Music tracks
├── background/         # Background audio
├── tmp/                # Temporary files
│   ├── encoded/        # Intermediate videos
│   ├── concat/         # Concat lists
│   └── audio/          # Audio loops
├── archive/            # Archived sources
└── final_*.mp4        # Output videos
```

### Custom Paths

```json
{
    "paths": {
        "tmp_dir": "/tmp/autovideo",
        "music_dir": "~/Music",
        "background_dir": "~/Backgrounds",
        "output_dir": "~/Videos"
    }
}
```

### RAM Disk Path

**Linux (tmpfs):**
```python
from video_renderer.config import get_ramdisk_path

ramdisk = get_ramdisk_path()
# Returns: /dev/shm/video_render_tmp (if 10GB+ free)
#          None (otherwise)
```

**Windows (manual setup):**
```python
# Use ImDisk or similar to create RAM disk
# Update config:
tmp_dir = "R:\\autovideo_tmp"
```

---

## Validation

### Validate Config File

```bash
python -m video_renderer --validate-config
```

### Check Hardware Detection

```bash
python -m video_renderer --list-hw
```

### Health Check

```bash
python -m video_renderer --health-check
```

---

## Examples

### Minimum Config

```json
{
    "encoder": {
        "default_codec": "h264"
    }
}
```

### High Quality Config

```json
{
    "encoder": {
        "default_codec": "h265",
        "preset": "slow",
        "crf": 18
    },
    "render_mode": "high_vram"
}
```

### Maximum Performance Config

```json
{
    "encoder": {
        "default_codec": "av1",
        "preset": "6",
        "crf": 28
    },
    "render_mode": "ramdisk",
    "gpu": {
        "surfaces": 128,
        "extra_frames": 16
    }
}
```

---

**Last Updated:** 2025-02-06
**Version:** 1.0.0
