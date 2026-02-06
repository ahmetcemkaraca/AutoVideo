# AutoVideo v1.0.0 - Installation Guide
**Version**: 1.0.0
**Last Updated**: 2025-02-06
**Languages**: English | [Türkçe](INSTALLATION_GUIDE_TR.md)

---

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Prerequisites](#prerequisites)
3. [Installation Methods](#installation-methods)
4. [Verification](#verification)
5. [Platform-Specific Instructions](#platform-specific-instructions)
6. [Troubleshooting](#troubleshooting)
7. [Uninstallation](#uninstallation)

---

## System Requirements

### Minimum Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **OS** | Windows 10+, macOS 10.15+, Ubuntu 20.04+ | Windows 11, macOS 13+, Ubuntu 22.04+ |
| **Python** | 3.10+ | 3.11+ |
| **RAM** | 4GB | 8GB+ |
| **Disk Space** | 10GB | 50GB+ SSD |
| **GPU** | None | NVIDIA (NVENC) or Intel (QSV) |

### Supported Platforms

- **Windows**: 10/11 (x64)
- **macOS**: 10.15+ (Intel & Apple Silicon)
- **Linux**: Ubuntu 20.04+, Debian 11+, Fedora 35+

---

## Prerequisites

### 1. FFmpeg Installation

FFmpeg is **required** for video processing.

#### Windows

1. Download FFmpeg from [ffmpeg.org](https://ffmpeg.org/download.html#build-windows)
2. Extract to `C:\ffmpeg`
3. Add to PATH:
   ```powershell
   # Open System Environment Variables
   # Add "C:\ffmpeg\bin" to PATH
   ```
4. Verify:
   ```cmd
   ffmpeg -version
   ```

#### macOS

```bash
# Using Homebrew (recommended)
brew install ffmpeg

# Or using MacPorts
sudo port install ffmpeg
```

#### Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install ffmpeg ffprobe -y
```

#### Linux (Fedora)

```bash
sudo dnf install ffmpeg -y
```

### 2. Python Installation

#### Windows

1. Download from [python.org](https://www.python.org/downloads/)
2. Run installer with **"Add Python to PATH"** checked
3. Verify:
   ```cmd
   python --version
   ```

#### macOS

```bash
# Using Homebrew
brew install python@3.11

# Verify
python3 --version
```

#### Linux

```bash
# Ubuntu/Debian
sudo apt install python3.11 python3.11-venv -y

# Fedora
sudo dnf install python3.11 python3.11-pip -y
```

---

## Installation Methods

### Method 1: pip (Recommended)

```bash
# Clone repository
git clone https://github.com/ahmetcemkaraca/AutoVideo.git
cd AutoVideo

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install AutoVideo
pip install -e .
```

### Method 2: Poetry (Development)

```bash
# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -

# Clone repository
git clone https://github.com/ahmetcemkaraca/AutoVideo.git
cd AutoVideo

# Install dependencies
poetry install

# Activate shell
poetry shell
```

### Method 3: Docker (Containerized)

```bash
# Build image
docker build -t autovideo:1.0.0 .

# Run container
docker run -it --gpus all \
  -v $(pwd)/videos:/workspace/videos \
  -v $(pwd)/output:/workspace/output \
  autovideo:1.0.0 --tui
```

---

## Verification

### 1. Check Python Version

```bash
python --version
# Expected: Python 3.10.0 or higher
```

### 2. Check FFmpeg

```bash
ffmpeg -version
ffprobe -version
```

### 3. Check AutoVideo Installation

```bash
python -m video_renderer --help
```

### 4. Test Hardware Acceleration

```bash
python -m video_renderer --list-hw
```

Expected output:
```
Available Hardware Encoders:
- NVIDIA NVENC: h264_nvenc, hevc_nvenc, av1_nvenc
- Intel QSV: h264_qsv, hevc_qsv, av1_qsv
- VAAPI: h264_vaapi, hevc_vaapi
```

### 5. Run Test Suite

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=video_renderer --cov-report=html

# View coverage report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

---

## Platform-Specific Instructions

### Windows

#### GPU Acceleration (NVIDIA)

1. Install [CUDA Toolkit](https://developer.nvidia.com/cuda-downloads)
2. Install latest NVIDIA drivers
3. Verify NVENC availability:
   ```cmd
   ffmpeg -hide_banner -encoders | findstr nvenc
   ```

#### Google Drive Setup

1. Place `client_secrets.json` in project root
2. First run will open browser for authentication
3. Token will be saved for future use

### macOS

#### Apple Silicon (M1/M2/M3)

FFmpeg with VideoToolbox (hardware acceleration):
```bash
brew install ffmpeg
```

#### GPU Acceleration (Intel)

No additional setup needed if using Intel Quick Sync.

### Linux

#### GPU Acceleration (NVIDIA)

```bash
# Install NVIDIA drivers
sudo apt install nvidia-driver-535

# Install CUDA Toolkit
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
sudo apt update
sudo apt install cuda-toolkit-12-2

# Verify
nvidia-smi
```

#### GPU Acceleration (Intel QSV)

```bash
# Ubuntu/Debian
sudo apt install intel-media-va-driver-non-free i965-va-driver-shaders

# Verify
vainfo
```

#### RAM Disk (Optional, for Ramtest Mode)

```bash
# Create tmpfs mount (Linux only)
sudo mkdir -p /dev/shm/autovideo
sudo mount -t tmpfs -o size=8G tmpfs /dev/shm/autovideo
```

---

## Configuration Files

After installation, create configuration file:

```bash
# Generate default config
python -m video_renderer --init-config

# Edit config.json
nano config.json  # Linux
vim config.json   # macOS
notepad config.json  # Windows
```

### Default Config Structure

```json
{
  "output_dir": "output",
  "temp_dir": "tmp",
  "default_codec": "libx264",
  "default_preset": "medium",
  "hardware_acceleration": true,
  "google_drive": {
    "enabled": false,
    "folder_id": null
  },
  "youtube": {
    "enabled": false,
    "default_privacy": "unlisted"
  }
}
```

---

## Troubleshooting

### Common Issues

#### Issue: "ffmpeg not found"

**Solution**:
1. Verify FFmpeg installation: `ffmpeg -version`
2. Check PATH environment variable
3. Restart terminal after PATH modification

#### Issue: "ModuleNotFoundError: No module named 'video_renderer'"

**Solution**:
```bash
# Reinstall in development mode
pip install -e .

# Or add project root to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"  # Linux/macOS
set PYTHONPATH="%PYTHONPATH%;%CD%"  # Windows
```

#### Issue: Hardware acceleration not working

**Solution**:
```bash
# List available encoders
python -m video_renderer --list-hw

# If empty, install drivers:
# - NVIDIA: Install CUDA and latest drivers
# - Intel: Install Media SDK
# - AMD: Install AMF drivers
```

#### Issue: "Permission denied" on Google Drive upload

**Solution**:
1. Remove old credentials: `rm youtube_credentials.json`
2. Re-authenticate: `python -m video_renderer --tui`
3. Grant Drive permissions when prompted

#### Issue: Out of memory during rendering

**Solution**:
1. Reduce chunk size in config
2. Use software encoding instead of hardware
3. Close other applications
4. Increase swap space (Linux)

### Getting Help

- [Documentation Index](../INDEX.md)
- [Troubleshooting Guide](TROUBLESHOOTING.md)
- [GitHub Issues](https://github.com/ahmetcemkaraca/AutoVideo/issues)
- [GitHub Discussions](https://github.com/ahmetcemkaraca/AutoVideo/discussions)

---

## Uninstallation

### Remove AutoVideo

```bash
# Deactivate virtual environment first
deactivate

# Remove package
pip uninstall autovideo

# Remove virtual environment
rm -rf venv  # Linux/macOS
rmdir /s venv  # Windows
```

### Remove Configuration Files

```bash
# Remove configs
rm config.json
rm -rf .autovideo/

# Remove credentials (optional)
rm youtube_credentials.json
rm oauth-credentials.json

# Remove logs
rm -rf logs/
```

### Remove FFmpeg

Follow platform-specific instructions:

**Windows**: Uninstall from "Add/Remove Programs"

**macOS**:
```bash
brew uninstall ffmpeg
```

**Linux**:
```bash
sudo apt remove ffmpeg ffprobe  # Ubuntu/Debian
sudo dnf remove ffmpeg  # Fedora
```

---

## Next Steps

After installation:

1. [Quick Start Guide](../README.md#quick-start)
2. [Configuration Reference](CONFIGURATION_REFERENCE.md)
3. [Usage Guide](../README.md#usage)
4. [API Documentation](../internal-docs/api/video-renderer-api.md)

---

## Installation Checklist

Use this checklist to verify your installation:

- [ ] Python 3.10+ installed
- [ ] FFmpeg installed and in PATH
- [ ] Virtual environment created
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] AutoVideo installed (`pip install -e .`)
- [ ] `python -m video_renderer --help` works
- [ ] Hardware acceleration detected (`--list-hw`)
- [ ] Test suite passes (`pytest`)
- [ ] Config file created (optional)

---

**Last Updated**: 2025-02-06
**Version**: 1.0.0
**Status**: Production Ready
