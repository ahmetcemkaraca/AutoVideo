# Validation Troubleshooting Guide

## Overview

This guide helps you diagnose and resolve common validation issues in the AutoVideo pipeline. It covers error messages, their causes, and step-by-step solutions.

## Common Validation Errors

### FFmpeg/ffprobe Related Errors

#### FFmpeg Not Found

**Error Messages:**
- `FFmpeg not found in PATH` (EN)
- `FFmpeg PATH'da bulunamadi` (TR)

**Symptoms:**
- All video validation fails
- Cannot extract video metadata
- Rendering cannot start

**Diagnosis:**
```bash
# Check if FFmpeg is installed
which ffmpeg
ffmpeg -version

# Check if ffprobe is available
which ffprobe
ffprobe -version
```

**Solutions:**

**Windows:**
```powershell
# Download FFmpeg
# 1. Go to https://ffmpeg.org/download.html
# 2. Download build for Windows
# 3. Extract to C:\ffmpeg

# Add to PATH (PowerShell - Admin)
[Environment]::SetEnvironmentVariable("Path", $env:Path + ";C:\ffmpeg\bin", "Machine")

# Verify
refreshenv
ffmpeg -version
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install ffmpeg

# Verify
ffmpeg -version | head -n 1
```

**Linux (Fedora):**
```bash
sudo dnf install ffmpeg ffmpeg-compat
```

**Linux (Arch):**
```bash
sudo pacman -S ffmpeg
```

**macOS:**
```bash
# Install Homebrew if not installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install FFmpeg
brew install ffmpeg

# Verify
ffmpeg -version | head -n 1
```

**Docker:**
```dockerfile
RUN apt-get update && apt-get install -y ffmpeg
```

#### FFprobe Timeout

**Error Messages:**
- `ffprobe timeout on video.mp4`
- `ffprobe zaman aşimi`

**Causes:**
1. Very large video file (>4GB)
2. Slow disk I/O (network drive, external HDD)
3. Corrupted video file
4. Insufficient system resources

**Solutions:**

**1. Increase Timeout:**
```python
from video_renderer.validator import VideoValidator
import subprocess

# Patch the timeout in get_video_info
original_run = subprocess.run

def custom_run(*args, timeout=60, **kwargs):
    """Increase timeout to 60 seconds."""
    return original_run(*args, timeout=timeout, **kwargs)

subprocess.run = custom_run
```

**2. Copy to Faster Storage:**
```bash
# Copy from network drive to local
cp /mnt/network/video.mp4 /tmp/video.mp4

# Validate local copy
python -c "from video_renderer.validator import quick_validate; print(quick_validate(Path('/tmp/video.mp4')))"
```

**3. Check File Integrity:**
```bash
# Test with FFmpeg
ffmpeg -v error -i video.mp4 -f null - 2>&1 | head -n 20

# Repair if corrupted
ffmpeg -i corrupted.mp4 -c copy repaired.mp4
```

#### FFprobe Returns Invalid JSON

**Error Messages:**
- `Failed to parse ffprobe output`
- `ffprobe çıktisi ayrıştırılamadı`

**Causes:**
1. Corrupted video file
2. Incompatible video format
3. FFmpeg version incompatibility

**Solutions:**

**1. Check FFprobe Output:**
```bash
ffprobe -v error -show_streams -show_format -of json video.mp4 | jq .

# If invalid JSON, check raw output
ffprobe -v error -show_streams -show_format video.mp4
```

**2. Test Video with FFmpeg:**
```bash
# Attempt to decode video
ffmpeg -v error -i video.mp4 -f null -

# Convert to standard format
ffmpeg -i problematic.mp4 -c:v libx264 -c:a aac fixed.mp4
```

**3. Update FFmpeg:**
```bash
# Check current version
ffmpeg -version | grep ffmpeg_version

# Update to latest
# Linux: sudo apt install --only-upgrade ffmpeg
# macOS: brew upgrade ffmpeg
```

### File System Errors

#### File Not Found

**Error Messages:**
- `Video dosyası bulunamadı: intro.mp4`
- `Intro file not found: intro.mp4`

**Causes:**
1. Incorrect file path
2. File has been moved or deleted
3. Case sensitivity mismatch
4. Permission denied

**Solutions:**

**1. Verify File Exists:**
```python
from pathlib import Path

file_path = Path("intro.mp4")

# Check existence
if not file_path.exists():
    print(f"File not found: {file_path.absolute()}")

    # Search for similar files
    parent = file_path.parent
    for f in parent.glob("*.mp4"):
        if file_path.stem.lower() in f.name.lower():
            print(f"Did you mean: {f.name}?")
```

**2. Check Case Sensitivity:**
```bash
# Linux is case-sensitive
ls -la intro.mp4
ls -la Intro.mp4
ls -la INTRO.MP4

# Find correct case
find . -iname "intro.mp4"
```

**3. Check Permissions:**
```bash
# Check file permissions
ls -la intro.mp4

# Fix permissions if needed
chmod 644 intro.mp4
```

**4. Use Absolute Path:**
```python
from pathlib import Path

# Use absolute path
video_path = Path("/full/path/to/intro.mp4").resolve()

if video_path.exists():
    print(f"Found: {video_path}")
```

#### Permission Denied

**Error Messages:**
- `Permission denied: /path/to/video.mp4`
- `Yazma izni yok`

**Causes:**
1. No read permission on file
2. No write permission on output directory
3. File owned by another user

**Solutions:**

**1. Check File Permissions:**
```bash
ls -la video.mp4

# Output: -rw-r--r-- 1 user group ...
#             |  |  |
#             |  |  +-- Others: read-only
#             |  +----- Group: read-only
#             +-------- Owner: read-write
```

**2. Fix Permissions:**
```bash
# Grant read permission
chmod +r video.mp4

# Grant write permission to directory
chmod +w /path/to/output

# Recursive permission fix
chmod -R u+rw /path/to/videos/*
```

**3. Change Ownership:**
```bash
# Take ownership (requires sudo)
sudo chown $USER:$USER video.mp4
sudo chown -R $USER:$USER /path/to/output
```

**4. Check Directory Write Access:**
```python
import os
import tempfile

output_dir = Path("/path/to/output")

# Check if directory exists
if not output_dir.exists():
    output_dir.mkdir(parents=True, exist_ok=True)

# Test write access
test_file = output_dir / ".write_test"
try:
    test_file.touch()
    test_file.unlink()
    print("Write access OK")
except PermissionError:
    print("No write permission")
```

### Disk Space Issues

#### Insufficient Disk Space

**Error Messages:**
- `Yetersiz disk alanı`
- `Insufficient disk space`
- `Tahmini yetersiz disk alanı`

**Diagnosis:**
```bash
# Check disk space
df -h

# Check specific directory
du -sh /path/to/output

# Find large files
du -ah /path/to/output | sort -rh | head -n 20
```

**Solutions:**

**1. Free Up Space:**
```bash
# Clean temporary files
rm -rf tmp/*.w64
rm -rf tmp/*.mp4
rm -rf tmp/validated_*

# Clear FFmpeg cache
rm -rf ~/.ffmpeg/

# Clean package cache (Linux)
sudo apt clean
sudo apt autoremove
```

**2. Archive Old Videos:**
```bash
# Create archive directory
mkdir -p archive/old

# Move old files
find final_*.mp4 -mtime +30 -exec mv {} archive/old/ \;

# Compress archive
tar -czf archive_$(date +%Y%m%d).tar.gz archive/old/
rm -rf archive/old/
```

**3. Change Output Directory:**
```python
from pathlib import Path
import shutil

# Check available space
def get_free_space_gb(path):
    stat = shutil.disk_usage(path)
    return stat.free / (1024**3)

# Find best drive
candidates = [
    Path("/output"),
    Path("/mnt/storage/output"),
    Path("D:/output")  # Windows
]

best = max(candidates, key=get_free_space_gb)
print(f"Best output: {best} ({get_free_space_gb(best):.1f} GB free)")
```

**4. Reduce Output Size:**
```python
# Lower bitrate for smaller files
config = {
    "video_bitrate": "2M",  # Reduced from 5M
    "audio_bitrate": "128k",  # Reduced from 192k
    "preset": "slower",  # Better compression
}
```

### Video Format Errors

#### Unsupported Codec

**Error Messages:**
- `Desteklenmeyen codec: mpeg4`
- `Unsupported codec: mpeg4`

**Causes:**
1. Source file uses unsupported codec
2. FFmpeg compiled without codec support
3. Codec name mismatch

**Diagnosis:**
```bash
# Check source codec
ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of default=noprint_wrappers=1:nokey=1 video.mp4

# Check supported codecs
ffmpeg -codecs | grep video
```

**Solutions:**

**1. Convert to Supported Codec:**
```bash
# Convert to H.264
ffmpeg -i input.mp4 -c:v libx264 -preset medium -crf 23 -c:a copy output.mp4

# Convert to H.265
ffmpeg -i input.mp4 -c:v libx265 -preset medium -crf 28 -c:a copy output.mp4

# Convert to AV1
ffmpeg -i input.mp4 -c:v libsvtav1 -preset 4 -crf 30 -c:a copy output.mp4
```

**2. Reinstall FFmpeg with Full Codec Support:**

**Linux:**
```bash
sudo apt install ffmpeg libavcodec-extra
```

**macOS:**
```bash
brew reinstall ffmpeg --with-libvpx --with-libx265 --with-libx264 --with-libavif
```

**From Source:**
```bash
# Download and compile with all codecs
wget https://ffmpeg.org/releases/ffmpeg-7.0.tar.gz
tar -xzf ffmpeg-7.0.tar.gz
cd ffmpeg-7.0
./configure --enable-gpl --enable-libx264 --enable-libx265 --enable-libvpx --enable-libaom
make -j$(nproc)
sudo make install
```

#### Resolution Mismatch

**Error Messages:**
- `Cozunurluk farkli: 3840x2160 -> 1920x1080`
- `Resolution mismatch: 3840x2160 -> 1920x1080`

**Impact:**
- Video will be re-encoded (quality loss)
- Longer rendering time
- Larger file size

**Solutions:**

**1. Accept Re-encoding:**
```python
# This is automatic - no action needed
# Video will be scaled to target resolution
```

**2. Pre-convert to Target Resolution:**
```bash
# Scale to 1080p
ffmpeg -i 4k_video.mp4 -vf scale=1920:1080 -c:v libx264 -preset medium -crf 23 -c:a copy 1080p_video.mp4

# Maintain aspect ratio
ffmpeg -i 4k_video.mp4 -vf scale=-1:1080 -c:v libx264 -preset medium -crf 23 -c:a copy 1080p_video.mp4

# Use lanczos for better quality
ffmpeg -i 4k_video.mp4 -vf scale=1920:1080:flags=lanczos -c:v libx264 -preset slow -crf 18 -c:a copy 1080p_video.mp4
```

**3. Change Target Resolution:**
```python
# Modify config to match source
config = {
    "width": 3840,  # Match source
    "height": 2160,
}
```

#### Pixel Format Issues

**Error Messages:**
- `Pixel format incompatible: yuv422p`
- `Pixel format uygun degil: yuv422p`

**Diagnosis:**
```bash
# Check pixel format
ffprobe -v error -select_streams v:0 -show_entries stream=pix_fmt -of default=noprint_wrappers=1:nokey=1 video.mp4
```

**Solutions:**

**1. Convert to Compatible Pixel Format:**
```bash
# Convert to yuv420p (8-bit)
ffmpeg -i input.mp4 -vf format=yuv420p -c:v libx264 -preset medium -crf 23 -c:a copy output.mp4

# Convert to yuv420p10le (10-bit for H.265/AV1)
ffmpeg -i input.mp4 -vf format=yuv420p10le -c:v libx265 -preset medium -crf 28 -c:a copy output.mp4

# Specify color space
ffmpeg -i input.mp4 -vf format=yuv420p,colorspace=bt709 -c:v libx264 -preset medium -crf 23 -c:a copy output.mp4
```

**2. Check Codec Compatibility:**
```python
# Valid pixel formats per codec
PIXEL_FORMATS = {
    "h264": ["yuv420p", "yuvj420p"],
    "hevc": ["yuv420p", "yuvj420p", "yuv420p10le", "yuv420p10"],
    "av1": ["yuv420p", "yuvj420p", "yuv420p10le", "yuv420p10"],
    "vp9": ["yuv420p", "yuvj420p"],
}
```

### Audio Validation Errors

#### Corrupted Audio File

**Error Messages:**
- `Donusturme hatasi: track.mp3`
- `Conversion error: track.mp3`

**Diagnosis:**
```bash
# Check audio file integrity
ffmpeg -v error -i track.mp3 -f null -

# Check with ffprobe
ffprobe -v error -show_format -show_streams track.mp3
```

**Solutions:**

**1. Attempt Repair:**
```bash
# Re-encode to fix corruption
ffmpeg -i corrupted.mp3 -c:a pcm_s16le repaired.wav

# Convert back to MP3
ffmpeg -i repaired.wav -c:a libmp3lame -b:a 320k fixed.mp3
```

**2. Re-download Source:**
```bash
# If downloaded from YouTube, etc.
# Re-download with different tool/quality
youtube-dl -f bestaudio --extract-audio --audio-format mp3 [URL]
```

**3. Use Alternative Format:**
```bash
# Convert FLAC/WAV to MP3
ffmpeg -i track.flac -c:a libmp3lame -b:a 320k track.mp3
```

#### Missing Metadata

**Warning Messages:**
- `Metadata not found: track.mp3`

**Solutions:**

**1. Add Metadata:**
```bash
# Add basic metadata
ffmpeg -i input.mp3 \
  -metadata title="Song Title" \
  -metadata artist="Artist Name" \
  -metadata album="Album Name" \
  -metadata genre="Genre" \
  -metadata year="2024" \
  -c:a copy \
  output.mp3
```

**2. Extract from Filename:**
```python
from pathlib import Path
import re

def extract_metadata_from_filename(filename):
    """Extract metadata from filename like 'Artist - Song.mp3'"""
    name = filename.stem
    if ' - ' in name:
        artist, title = name.split(' - ', 1)
        return {"artist": artist.strip(), "title": title.strip()}
    return {}

# Use with AudioProcessor
metadata = extract_metadata_from_filename(Path("Artist - Song.mp3"))
```

### Duration Mismatch

#### Target Duration Not Met

**Warning Messages:**
- `Sure farki tespit edildi`
- `Duration difference detected`

**Details:**
- `Hedef: 3600s, Gercek: 3598.5s, Fark: 1.5s`

**Causes:**
1. Loop doesn't divide evenly into target duration
2. Source video duration is slightly off
3. Audio track length mismatch

**Solutions:**

**1. Accept Within Tolerance:**
```python
# Default tolerance is ±5 seconds
# This is normal and acceptable
```

**2. Adjust Tolerance:**
```python
from video_renderer.validator import PostRenderValidator

# Increase tolerance to 10 seconds
validator = PostRenderValidator(duration_tolerance=10.0)
```

**3. Adjust Loop Count:**
```python
# Calculate more precise loop count
import math

target_duration = 3600
loop_duration = 45.2

# More precise calculation
loop_count = math.ceil(target_duration / loop_duration)
actual_duration = loop_count * loop_duration

print(f"Loop count: {loop_count}")
print(f"Actual duration: {actual_duration:.1f}s")
```

## Platform-Specific Issues

### Windows

#### Long Path Names

**Error:**
- `File name too long`
- Path exceeds 260 characters

**Solutions:**

```python
# Use long path prefix
from pathlib import Path

def make_long_path(path):
    """Enable long path support on Windows."""
    path_str = str(path)
    if not path_str.startswith('\\\\?\\'):
        return Path('\\\\?\\' + path_str)
    return path

long_path = make_long_path(Path("C:/very/long/path/.../video.mp4"))
```

**Enable Long Path Support (Windows 10+):**
```powershell
# Enable long paths (Admin PowerShell)
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
```

#### FFmpeg Path Issues

**Error:**
- `ffmpeg is not recognized as an internal or external command`

**Solutions:**

```python
import os
import shutil

def find_ffmpeg():
    """Find FFmpeg executable on Windows."""
    # Check common installation paths
    candidates = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
    ]

    for path in candidates:
        if Path(path).exists():
            return path

    # Check PATH
    ffmpeg_path = shutil.which("ffmpeg.exe")
    if ffmpeg_path:
        return ffmpeg_path

    return None

ffmpeg_path = find_ffmpeg()
if ffmpeg_path:
    print(f"Found FFmpeg at: {ffmpeg_path}")
else:
    print("FFmpeg not found. Please install.")
```

### Linux

#### Missing Codec Libraries

**Error:**
- `Unknown codec 'h264_mediacodec'`
- `Codec not supported`

**Diagnosis:**
```bash
# Check FFmpeg configuration
ffmpeg -version | grep configuration

# Look for codec support
ffmpeg -codecs | grep -E "h264|h265|av1|vp9"
```

**Solutions:**

```bash
# Ubuntu/Debian - Install extra codecs
sudo apt update
sudo apt install ffmpeg libavcodec-extra

# Verify codec support
ffmpeg -codecs | grep h264
```

#### Permission Denied on /dev/

**Error:**
- `Permission denied /dev/snd/`
- `Cannot access audio device`

**Solutions:**

```bash
# Add user to audio group
sudo usermod -a -G audio $USER

# Log out and back in for changes to take effect

# Verify
groups
```

### macOS

#### Gatekeeper Blocking FFmpeg

**Error:**
- `ffmpeg cannot be opened because the developer cannot be verified`

**Solutions:**

```bash
# Remove quarantine attribute
xattr -cr /usr/local/bin/ffmpeg
xattr -cr /usr/local/bin/ffprobe

# Or allow in System Preferences
# System Preferences > Security & Privacy > Allow apps downloaded from: App Store and identified developers
```

#### M1/M2 Apple Silicon Issues

**Error:**
- FFmpeg not optimized for Apple Silicon

**Solutions:**

```bash
# Install native ARM version
brew reinstall ffmpeg

# Verify architecture
uname -m  # Should show arm64
file $(which ffmpeg)  # Should show ARM64 Mach-O
```

## Debug Tips

### Enable Verbose Logging

```python
import logging

# Enable debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Or for specific module
logging.getLogger('video_renderer.validator').setLevel(logging.DEBUG)
```

### Test FFprobe Commands Manually

```bash
# Test video info extraction
ffprobe -v error -show_streams -show_format -of json video.mp4 | jq '.'

# Test specific stream
ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,height -of default=noprint_wrappers=1:nokey=1 video.mp4

# Test duration
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 video.mp4
```

### Check File Integrity

```bash
# Verify video file
ffmpeg -v error -i video.mp4 -f null - 2>&1 | less

# Count errors
ffmpeg -v error -i video.mp4 -f null - 2>&1 | grep -c error

# Check for corruption
ffmpeg -v error -err_detect explode -i video.mp4 -f null -
```

### Monitor Disk I/O

```bash
# Linux - monitor disk usage during validation
iotop -o

# Watch disk space
watch -n 5 df -h

# Check file handles
lsof | grep ffmpeg
```

### Profile Validation Performance

```python
import time
from contextlib import contextmanager

@contextmanager
def timer(name):
    """Context manager for timing operations."""
    start = time.time()
    yield
    elapsed = time.time() - start
    print(f"{name}: {elapsed:.2f}s")

# Use with validation
with timer("Video validation"):
    result = validator.validate_output(video_path, specs)

with timer("Audio validation"):
    result = processor.validate_tracks(tracks)
```

## Getting Help

### Collect Diagnostic Information

```python
import sys
import platform
import subprocess
from pathlib import Path

def collect_diagnostics():
    """Collect system and validation diagnostics."""
    info = {
        "python": sys.version,
        "platform": platform.platform(),
        "ffmpeg": None,
        "ffprobe": None,
        "disk_space": None,
    }

    # Check FFmpeg
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        info["ffmpeg"] = result.stdout.split('\n')[0]
    except FileNotFoundError:
        info["ffmpeg"] = "Not found"

    # Check ffprobe
    try:
        result = subprocess.run(["ffprobe", "-version"], capture_output=True, text=True)
        info["ffprobe"] = result.stdout.split('\n')[0]
    except FileNotFoundError:
        info["ffprobe"] = "Not found"

    # Disk space
    import shutil
    disk = shutil.disk_usage(".")
    info["disk_space"] = {
        "free_gb": disk.free / (1024**3),
        "used_gb": disk.used / (1024**3),
        "total_gb": disk.total / (1024**3),
    }

    return info

# Print diagnostics
import json
print(json.dumps(collect_diagnostics(), indent=2))
```

### Create Minimal Reproducible Example

```python
from video_renderer.validator import VideoValidator
from pathlib import Path

def create_reproducer():
    """Create a minimal reproducible example for bug reports."""

    # Sample file path
    video_path = Path("problematic_video.mp4")

    # Validator configuration
    validator = VideoValidator(
        duration_tolerance=5.0,
        fps_tolerance=0.1,
    )

    # Validation specs
    specs = {
        "duration_seconds": 3600,
        "width": 1920,
        "height": 1080,
        "fps": 60,
        "codec": "h264",
        "has_audio": True,
    }

    # Run validation
    result = validator.validate_output(video_path, specs)

    # Export result
    from video_renderer.validator import export_validation_report
    report_path = export_validation_report(result)

    print(f"Validation report saved to: {report_path}")
    print(f"Result valid: {result.valid}")
    print(f"Errors: {len(result.errors)}")
    print(f"Warnings: {len(result.warnings)}")

    return report_path
```

### Submit Bug Report

When submitting a bug report, include:

1. **System Information:**
   - Operating system and version
   - Python version
   - FFmpeg version

2. **Validation Report:**
   - Export validation report (JSON)
   - Include full error messages (both EN and TR)

3. **Sample Files:**
   - If possible, provide a sample file that reproduces the issue
   - Or provide ffprobe output: `ffprobe -v error -show_streams -show_format -of json video.mp4`

4. **Steps to Reproduce:**
   ```python
   # 1. Run this code
   from video_renderer.validator import validate_before_render

   result = validate_before_render(
       intro_path=Path("intro.mp4"),
       loop_path=Path("loop.mp4"),
       single_path=None,
       tracks=[Path("music.mp3")],
       target_duration=3600,
       output_dir=Path("output")
   )

   # 2. Expected: Success
   # 3. Actual: Validation fails with error "..."
   ```

## Additional Resources

- **User Guide:** `docs/video-validation.md`
- **Architecture:** `docs/internal-docs/validation/architecture.md`
- **FFmpeg Documentation:** https://ffmpeg.org/documentation.html
- **FFprobe Documentation:** https://ffmpeg.org/ffprobe.html
- **FFmpeg Bug Tracker:** https://trac.ffmpeg.org/

---

**Last Updated:** 2026-02-06

**Version:** 1.0
