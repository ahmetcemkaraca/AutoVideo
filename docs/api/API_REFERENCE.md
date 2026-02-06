# Troubleshooting Guide

Common issues and solutions for AutoVideo v1.0.0.

---

## Table of Contents

- [Installation Issues](#installation-issues)
- [FFmpeg Issues](#ffmpeg-issues)
- [Hardware Acceleration Issues](#hardware-acceleration-issues)
- [Rendering Issues](#rendering-issues)
- [Audio Issues](#audio-issues)
- [Batch Processing Issues](#batch-processing-issues)
- [Upload Issues](#upload-issues)
- [Performance Issues](#performance-issues)
- [Memory Issues](#memory-issues)
- [TUI Issues](#tui-issues)

---

## Installation Issues

### FFmpeg not found

**Error:**
```
ffmpeg: command not found
```

**Solution:**

Install FFmpeg for your operating system:

**Linux (Debian/Ubuntu):**
```bash
sudo apt update
sudo apt install ffmpeg
```

**Linux (Fedora):**
```bash
sudo dnf install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

**Windows:**
1. Download from https://ffmpeg.org/download.html
2. Extract to a folder (e.g., `C:\ffmpeg`)
3. Add to PATH:
   - Press Win+R, type `sysdm.cpl`
   - Go to Advanced → Environment Variables
   - Edit PATH and add `C:\ffmpeg\bin`

**Verify:**
```bash
ffmpeg -version
ffprobe -version
```

### Python version too old

**Error:**
```
ERROR: This package requires Python 3.10 or later
```

**Solution:**

Install Python 3.10+:

**Linux:**
```bash
# Ubuntu/Debian
sudo apt install python3.10

# Fedora
sudo dnf install python3.10
```

**macOS:**
```bash
brew install python@3.10
```

**Windows:**
1. Download from https://www.python.org/downloads/
2. Install Python 3.10 or later
3. Check "Add Python to PATH" during installation

**Verify:**
```bash
python --version
# Should show 3.10 or later
```

### Dependencies installation failed

**Error:**
```
ERROR: Could not find a version that satisfies the requirement textual>=0.40.0
```

**Solution:**

Update pip and install dependencies:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Permission denied

**Error:**
```
Permission denied: '/usr/local/lib/python3.10/dist-packages'
```

**Solution:**

Use virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

---

## FFmpeg Issues

### Hardware encoder not found

**Error:**
```
Error initializing output stream 0:0 -- Error while opening encoder for output stream #0:0 - maybe incorrect parameters such as bit_rate, rate, width or height
```

**Solution:**

1. Check available encoders:
```bash
python -m video_renderer --list-hw
```

2. If hardware encoder not detected, the system falls back to software encoding automatically.

3. To force software encoding:
```bash
python -m video_renderer --no-hw-accel
```

### FFmpeg timeout

**Error:**
```
subprocess.TimeoutExpired: Command 'ffmpeg' timed out
```

**Solution:**

Hardware detection timeout can be increased. The default is 5 seconds. If you have slow hardware, the system will automatically fall back to software encoding.

**Verify:**
```bash
# Test encoder manually
ffmpeg -hide_banner -f lavfi -i color=black:s=64x64:d=0.04 -c:v h264_nvenc -t 0.04 -f null -
```

### FFmpeg hangs during rendering

**Symptoms:**
- Progress stops updating
- High CPU/GPU usage but no progress
- Process doesn't respond to cancel

**Solution:**

1. Use `--verbose` flag to see detailed logs:
```bash
python -m video_renderer --tui --verbose
```

2. Check FFmpeg logs in `tmp/ffmpeg.log`

3. Try reducing GPU buffer usage:
```bash
python -m video_renderer --tui --mode standard
```

---

## Hardware Acceleration Issues

### NVIDIA NVENC not detected

**Error:**
```
Hardware encoder 'h264_nvenc' not available
```

**Possible causes:**
1. NVIDIA drivers not installed
2. GPU too old (GTX 10-series+ required)
3. NVIDIA drivers too old

**Solution:**

1. Check GPU:
```bash
nvidia-smi
```

2. Update drivers:
- Linux: `sudo apt install nvidia-driver-535`
- Windows: Download from NVIDIA website

3. Verify encoder:
```bash
ffmpeg -hide_banner -encoders | grep nvenc
```

### Intel QSV not detected

**Error:**
```
Hardware encoder 'h264_qsv' not available
```

**Possible causes:**
1. Intel media drivers not installed
2. CPU too old (4th Gen+ required)
3. Missing media-sdk

**Solution:**

**Linux (Intel):**
```bash
sudo apt install intel-media-va-driver-non-free
```

**Windows:**
Install Intel Media SDK from Intel website

### VAAPI not detected (Linux)

**Error:**
```
Hardware encoder 'h264_vaapi' not available
```

**Possible causes:**
1. VAAPI drivers not installed
2. Wrong device path

**Solution:**

```bash
# Install VAAPI drivers
sudo apt install vainfo

# Verify VAAPI
vainfo

# Check render device
ls -la /dev/dri/
```

### GPU fallback chain fails

**Error:**
```
No suitable encoder found
```

**Solution:**

Force software encoding:

```bash
python -m video_renderer --no-hw-accel
```

Or specify codec explicitly:

```bash
python -m video_renderer --codec h264
```

---

## Rendering Issues

### Video compatibility check failed

**Error:**
```
CompatibilityError: Video is not compatible
```

**Possible reasons:**
- Wrong resolution
- Wrong FPS
- Unsupported pixel format

**Solution:**

1. Check video info:
```bash
ffprobe -v error -show_entries stream=width,height,r_frame_rate,pix_fmt -of default=noprint_wrappers=1 input.mp4
```

2. Normalize video automatically (the system does this by default)

3. Check requirements:
- Resolution: 1920x1080 (default)
- FPS: 60 or 59.94
- Pixel format: yuv420p

### Output video corrupted

**Symptoms:**
- Video doesn't play
- Glitches in playback
- Audio out of sync

**Solution:**

1. Check temp files:
```bash
ls -lh tmp/encoded/
ls -lh tmp/concat/
```

2. Re-run with verbose logging:
```bash
python -m video_renderer --tui --debug
```

3. Check FFmpeg logs:
```bash
cat tmp/ffmpeg.log
```

4. Try different codec:
```bash
python -m video_renderer --codec h264
```

### Concatenation fails

**Error:**
```
Concat failed: Invalid data
```

**Possible causes:**
1. Videos have different codecs
2. Videos have different resolutions
3. Videos have different FPS

**Solution:**

The system automatically normalizes videos before concatenation. If normalization fails:

1. Check video compatibility:
```bash
ffprobe video1.mp4
ffprobe video2.mp4
```

2. Manually normalize:
```bash
ffmpeg -i input.mp4 -c:v libx264 -preset fast -crf 20 -vf scale=1920:1080 -r 60 normalized.mp4
```

---

## Audio Issues

### Audio track too short

**Error:**
```
Audio duration (1800s) is less than target (36000s)
```

**Solution:**

The system automatically loops audio to match target duration. If you see this warning, it's informational only.

### Audio format not supported

**Error:**
```
AudioValidationError: Unsupported audio format
```

**Supported formats:**
- MP3
- WAV
- FLAC
- OGG
- M4A
- AAC
- WMA

**Solution:**

Convert to supported format:

```bash
ffmpeg -i input.aac -c:a mp3 output.mp3
```

### Audio mixing fails

**Error:**
```
AudioError: Failed to mix tracks
```

**Possible causes:**
1. Different sample rates
2. Different bit depths
3. Corrupted audio files

**Solution:**

1. Validate tracks:
```python
from video_renderer.audio import AudioProcessor

processor = AudioProcessor()
valid_tracks = processor.validate_tracks(track_paths)
```

2. Check audio files:
```bash
ffprobe -v error -show_entries stream=codec_name,sample_rate,bits_per_sample track1.mp3
```

### No audio in output

**Symptoms:**
- Video plays but no sound
- Audio track missing

**Solution:**

1. Check if audio processing completed:
```bash
ls -lh tmp/audio/
```

2. Verify audio file exists:
```bash
ls -lh tmp/final_audio.w64
```

3. Check FFmpeg mux command in logs

---

## Batch Processing Issues

### Batch queue stuck

**Symptoms:**
- Queue shows "running" but no progress
- Jobs not starting

**Solution:**

1. Check for stale locks:
```bash
ls -la tmp/*.lock
```

2. Remove stale locks:
```bash
rm tmp/*.lock
```

3. Restart batch processing

### Batch job fails silently

**Symptoms:**
- Job marked as failed
- No error message

**Solution:**

1. Check logs:
```bash
cat tmp/batch.log
```

2. Enable debug mode:
```bash
python -m video_renderer --batch --debug
```

3. Check job status:
```python
from video_renderer.batch import BatchQueue

queue = BatchQueue.load()
for job in queue.jobs:
    print(f"Job {job.id}: {job.status}, Error: {job.error}")
```

### Auto-detection not finding pairs

**Symptoms:**
- Smart batch finds 0 pairs
- Known intro/loop files not detected

**Solution:**

1. Check default patterns:
```python
from video_renderer.batch import SmartBatchDetector

detector = SmartBatchDetector()
print(detector.patterns)  # ['_intro', '-intro', 'intro']
```

2. Rename files to match patterns:
```
video_intro.mp4  /  video_loop.mp4
video-intro.mp4  /  video-loop.mp4
videoIntro.mp4   /  videoLoop.mp4
```

3. Use custom patterns:
```python
detector = SmartBatchDetector(patterns=["_start", "_begin"])
```

---

## Upload Issues

### Google Drive authentication failed

**Error:**
```
AuthenticationError: Failed to authenticate with Google Drive
```

**Solution:**

1. Re-authenticate:
```bash
python -m video_renderer --auth-drive
```

2. Clear credentials:
```bash
rm ~/.config/autovideo/credentials.json
```

3. Re-run authentication

### Upload fails with timeout

**Error:**
```
UploadError: Upload timeout
```

**Solution:**

1. Check network connection
2. Reduce file size
3. Try upload during off-peak hours

### YouTube upload rejected

**Error:**
```
YouTubeError: Upload rejected
```

**Possible causes:**
1. Invalid metadata
2. Video too long (>12 hours)
3. Account quota exceeded

**Solution:**

1. Check metadata:
```python
metadata = {
    "title": "My Video",
    "description": "Description",
    "tags": ["tag1", "tag2"],
    "privacy": "unlisted"
}
```

2. Check YouTube quota:
- Go to YouTube Studio
- Check upload status

---

## Performance Issues

### Slow encoding speed

**Symptoms:**
- Encoding at <1x speed
- Long render times

**Solution:**

1. Check hardware acceleration:
```bash
python -m video_renderer --list-hw
```

2. Use faster preset:
```bash
python -m video_renderer --preset fast
```

3. Use hardware encoder:
```bash
python -m video_renderer --hw-accel
```

4. Check GPU usage:
```bash
nvidia-smi  # NVIDIA
```

### High CPU usage

**Symptoms:**
- CPU at 100%
- System unresponsive

**Solution:**

1. Reduce concurrent jobs:
```bash
export AUTORENDER_MAX_CONCURRENT=1
```

2. Use hardware acceleration:
```bash
python -m video_renderer --hw-accel
```

3. Use faster preset:
```bash
python -m video_renderer --preset fast
```

### Disk I/O bottleneck

**Symptoms:**
- High disk usage
- Slow encoding despite low CPU/GPU

**Solution:**

1. Use RAM disk mode:
```bash
python -m video_renderer --mode ramdisk
```

2. Move temp files to faster disk:
```bash
export AUTORENDER_TMP_DIR=/mnt/ssd/autovideo_tmp
```

---

## Memory Issues

### Out of memory error

**Error:**
```
MemoryError: Unable to allocate memory
```

**Solution:**

1. Use ramtest mode:
```bash
python -m video_renderer --mode ramtest
```

2. Reduce GPU buffers:
```bash
python -m video_renderer --mode standard
```

3. Reduce batch size:
```bash
export AUTORENDER_MAX_CONCURRENT=1
```

### Memory leak during long render

**Symptoms:**
- Memory usage increases over time
- System becomes unresponsive

**Solution:**

1. Use ramtest mode for monitoring:
```bash
python -m video_renderer --mode ramtest
```

2. Enable memory tracking:
```bash
export AUTORENDER_TRACK_MEMORY=true
```

3. Check for leaks in logs

---

## TUI Issues

### TUI not rendering correctly

**Symptoms:**
- garbled display
- Missing colors
- Wrong alignment

**Solution:**

1. Check terminal compatibility:
```bash
echo $TERM
```

2. Use modern terminal:
- Windows Terminal (Windows)
- iTerm2 (macOS)
- GNOME Terminal (Linux)

3. Resize terminal to minimum 80x24

### TUI freezes

**Symptoms:**
- TUI not responding
- No keyboard input working

**Solution:**

1. Press `q` to quit
2. If frozen, force quit:
```bash
killall python
```

3. Check for deadlocks in logs

### Progress bar not updating

**Symptoms:**
- Progress stuck at 0%
- No status updates

**Solution:**

1. Check if render is actually running:
```bash
ps aux | grep ffmpeg
```

2. Check logs:
```bash
tail -f tmp/ffmpeg.log
```

3. Re-render with `--verbose` flag

---

## Getting Help

If you're still experiencing issues:

### 1. Gather System Information

```bash
python -m video_renderer --health-check
```

### 2. Collect Logs

```bash
# Main log
cat ~/.config/autovideo/app.log

# FFmpeg log
cat tmp/ffmpeg.log

# Batch log
cat tmp/batch.log
```

### 3. Create Debug Report

```bash
python -m video_renderer --debug-report > debug_report.txt
```

### 4. Report Issue

Include in your report:
- System information (from health check)
- Error messages
- Logs (sanitized)
- Steps to reproduce
- Configuration (sanitized)

**Report to:** [GitHub Issues](https://github.com/ahmetcemkaraca/AutoVideo/issues)

---

**Last Updated:** 2025-02-06
**Version:** 1.0.0
