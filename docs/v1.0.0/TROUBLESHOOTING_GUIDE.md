# AutoVideo v1.0.0 - Troubleshooting Guide
**Version**: 1.0.0
**Last Updated**: 2025-02-06

---

## Table of Contents

1. [Quick Diagnostics](#quick-diagnostics)
2. [Common Issues](#common-issues)
3. [Installation Issues](#installation-issues)
4. [Rendering Issues](#rendering-issues)
5. [Audio Issues](#audio-issues)
6. [Cloud Integration Issues](#cloud-integration-issues)
7. [Performance Issues](#performance-issues)
8. [Hardware Acceleration Issues](#hardware-acceleration-issues)
9. [Debug Mode](#debug-mode)
10. [Getting Help](#getting-help)

---

## Quick Diagnostics

### Health Check Command

```bash
python -m video_renderer --health-check
```

This will check:
- FFmpeg installation and version
- Python version and dependencies
- Hardware encoder availability
- Disk space
- Memory availability
- Configuration validity

### Diagnostic Information

```bash
# Show system info
python -m video_renderer --system-info

# List available encoders
python -m video_renderer --list-hw

# Show configuration
python -m video_renderer --show-config

# Test installation
python -m video_renderer --test-install
```

---

## Common Issues

### Issue: "ffmpeg not found"

**Symptoms**:
```
FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'
```

**Solutions**:

1. **Check if FFmpeg is installed**:
   ```bash
   ffmpeg -version
   ```

2. **If not installed**:
   - **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH
   - **macOS**: `brew install ffmpeg`
   - **Linux**: `sudo apt install ffmpeg`

3. **If installed but not found**:
   - **Windows**: Add `C:\ffmpeg\bin` to System PATH
   - **macOS/Linux**: Ensure `/usr/local/bin` is in PATH
   - Restart terminal after PATH changes

4. **Verify in Python**:
   ```bash
   python -c "import shutil; print(shutil.which('ffmpeg'))"
   ```

---

### Issue: "ModuleNotFoundError: No module named 'video_renderer'"

**Symptoms**:
```
ModuleNotFoundError: No module named 'video_renderer'
```

**Solutions**:

1. **Install in development mode**:
   ```bash
   pip install -e .
   ```

2. **Check Python path**:
   ```bash
   # Show Python path
   python -c "import sys; print('\n'.join(sys.path))"
   ```

3. **Add to PYTHONPATH** (temporary):
   ```bash
   # Linux/macOS
   export PYTHONPATH="${PYTHONPATH}:$(pwd)"

   # Windows
   set PYTHONPATH="%PYTHONPATH%;%CD%"
   ```

4. **Reinstall dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

---

### Issue: "Permission denied" errors

**Symptoms**:
```
PermissionError: [Errno 13] Permission denied: 'output/video.mp4'
```

**Solutions**:

1. **Check directory permissions**:
   ```bash
   # Linux/macOS
   ls -la output/

   # Windows
   icacls output
   ```

2. **Fix permissions**:
   ```bash
   # Linux/macOS
   chmod 755 output/

   # Windows (run as Administrator)
   icacls output /grant Users:F
   ```

3. **Use different output directory**:
   ```bash
   python -m video_renderer --output-dir ~/Videos/output --tui
   ```

---

### Issue: "Out of memory"

**Symptoms**:
- Rendering stops mid-way
- System becomes unresponsive
- `MemoryError` in Python

**Solutions**:

1. **Reduce concurrent jobs**:
   ```json
   {
     "batch": {
       "max_concurrent": 1
     }
   }
   ```

2. **Enable ramtest mode** (for large files):
   ```bash
   python -m video_renderer --rm --tui
   ```

3. **Use software encoding** (uses less GPU memory):
   ```bash
   python -m video_renderer --codec libx264 --tui
   ```

4. **Close other applications**
5. **Increase swap space** (Linux):
   ```bash
   sudo fallocate -l 8G /swapfile
   sudo chmod 600 /swapfile
   sudo mkswap /swapfile
   sudo swapon /swapfile
   ```

---

### Issue: "Out of disk space"

**Symptoms**:
```
OSError: [Errno 28] No space left on device
```

**Solutions**:

1. **Check disk space**:
   ```bash
   # Linux/macOS
   df -h

   # Windows
   wmic logicaldisk get size,freespace,caption
   ```

2. **Clean temporary files**:
   ```bash
   # Clean tmp directory
   rm -rf tmp/*

   # Clean old renders
   rm output/final_*.mp4
   ```

3. **Change output directory**:
   ```json
   {
     "core": {
       "output_dir": "/path/to/drive/with/space"
     }
   }
   ```

4. **Archive old files**:
   ```bash
   python -m video_renderer --archive-old
   ```

---

## Installation Issues

### Issue: pip install fails

**Symptoms**:
```
ERROR: Could not build wheels for some packages
```

**Solutions**:

1. **Upgrade pip**:
   ```bash
   pip install --upgrade pip
   ```

2. **Use system package manager**:
   ```bash
   # Ubuntu/Debian
   sudo apt install python3-pip python3-venv

   # macOS
   brew install python@3.11
   ```

3. **Install dependencies manually**:
   ```bash
   # Install each dependency
   pip install textual rich pydantic
   pip install google-api-python-client google-auth-oauthlib
   ```

### Issue: Virtual environment won't activate

**Symptoms**:
- `venv\Scripts\activate` not found (Windows)
- `source venv/bin/activate` fails (Linux/macOS)

**Solutions**:

1. **Recreate virtual environment**:
   ```bash
   rm -rf venv
   python -m venv venv
   ```

2. **Use Python venv module directly**:
   ```bash
   python -m venv venv
   ```

3. **Check Python installation**:
   ```bash
   python -m venv --help
   ```

---

## Rendering Issues

### Issue: Video encoding fails immediately

**Symptoms**:
```
FFmpegError: Encoding failed with exit code 1
```

**Solutions**:

1. **Check video compatibility**:
   ```bash
   ffprobe intro.mp4
   ffprobe loop.mp4
   ```

2. **Verify codec support**:
   ```bash
   ffmpeg -codecs | grep h264
   ```

3. **Try different codec**:
   ```bash
   python -m video_renderer --codec libx264 --tui
   ```

4. **Enable debug mode**:
   ```bash
   python -m video_renderer --debug --tui
   ```

### Issue: Encoding stops at specific percentage

**Symptoms**:
- Progress stops at 50%, 75%, etc.
- No error message

**Solutions**:

1. **Check for corrupted files**:
   ```bash
   ffmpeg -v error -i intro.mp4 -f null -
   ```

2. **Disable hardware acceleration**:
   ```bash
   python -m video_renderer --no-hw-accel --tui
   ```

3. **Reduce quality preset**:
   ```bash
   python -m video_renderer --preset fast --tui
   ```

4. **Check disk space** during render

---

### Issue: Output video has wrong duration

**Symptoms**:
- Video is shorter/longer than expected
- Loop doesn't match target duration

**Solutions**:

1. **Check duration calculation**:
   ```bash
   # Show duration info
   python -m video_renderer --show-duration 8h
   ```

2. **Verify concat list**:
   ```bash
   cat tmp/concat_list.txt
   ```

3. **Check source video durations**:
   ```bash
   ffprobe -show_entries format=duration -v quiet -of csv="p=0" intro.mp4
   ffprobe -show_entries format=duration -v quiet -of csv="p=0" loop.mp4
   ```

4. **Recalculate manually**:
   ```python
   # Target: 8 hours = 28800 seconds
   # Intro: 30 seconds
   # Loop: 10 seconds
   # Loops needed = (28800 - 30) / 10 = 2877
   ```

---

## Audio Issues

### Issue: Audio is out of sync

**Symptoms**:
- Audio doesn't match video
- Audio starts late/early

**Solutions**:

1. **Check source audio sync**:
   ```bash
   ffprobe -i intro.mp4 -show_entries stream=codec_type,duration,start_time
   ```

2. **Normalize audio**:
   ```json
   {
     "audio": {
       "normalize": true
     }
   }
   ```

3. **Re-encode audio**:
   ```bash
   python -m video_renderer --audio-codec aac --tui
   ```

### Issue: Background music too loud/quiet

**Symptoms**:
- Can't hear background music
- Background music drowns out main audio

**Solutions**:

1. **Adjust background gain**:
   ```json
   {
     "audio": {
       "background_gain": -15.0
     }
   }
   ```

2. **Use filename-based gain**:
   ```bash
   # File: bg_-10.mp3 → -10 dB gain
   # File: bg_-5.mp3 → -5 dB gain
   mv background_music.mp3 bg_-10.mp3
   ```

3. **Normalize audio levels**:
   ```bash
   ffmpeg -i input.mp3 -filter:a volumedetect -f null -
   ```

---

## Cloud Integration Issues

### Issue: Google Drive authentication fails

**Symptoms**:
```
AuthenticationError: Failed to authenticate with Google Drive
```

**Solutions**:

1. **Check client_secrets.json**:
   ```bash
   # File should exist in project root
   ls -l client_secrets.json
   ```

2. **Remove old credentials**:
   ```bash
   rm youtube_credentials.json
   rm oauth-credentials.json
   ```

3. **Re-authenticate**:
   ```bash
   python -m video_renderer --auth-drive
   ```

4. **Check permissions**:
   - Ensure Drive API is enabled
   - Check OAuth consent screen

### Issue: YouTube upload fails

**Symptoms**:
```
UploadError: Failed to upload to YouTube
```

**Solutions**:

1. **Check quota**:
   - YouTube has daily upload limits
   - Check [YouTube Dashboard](https://studio.youtube.com)

2. **Verify file size**:
   - Max file size: 256GB
   - Max duration: 12 hours

3. **Check network connection**:
   ```bash
   ping youtube.com
   ```

4. **Retry upload**:
   ```bash
   python -m video_renderer --upload-existing output/video.mp4
   ```

---

## Performance Issues

### Issue: Rendering is very slow

**Symptoms**:
- Encoding at < 1x speed
- Takes hours to render

**Solutions**:

1. **Enable hardware acceleration**:
   ```bash
   python -m video_renderer --hw-accel --tui
   ```

2. **Use faster preset**:
   ```bash
   python -m video_renderer --preset fast --tui
   ```

3. **Check hardware utilization**:
   ```bash
   # GPU (NVIDIA)
   nvidia-smi

   # CPU
   top
   ```

4. **Reduce output quality**:
   ```json
   {
     "encoder": {
       "preset": "veryfast",
       "crf": 28
     }
   }
   ```

### Issue: High CPU usage

**Symptoms**:
- CPU at 100%
- System sluggish

**Solutions**:

1. **Switch to GPU encoding**:
   ```bash
   python -m video_renderer --codec h264_nvenc --tui
   ```

2. **Reduce concurrent jobs**:
   ```json
   {
     "batch": {
       "max_concurrent": 1
     }
   }
   ```

3. **Set process priority** (Windows):
   ```bash
   # Run with low priority
   start /low python -m video_renderer --tui
   ```

---

## Hardware Acceleration Issues

### Issue: NVIDIA NVENC not available

**Symptoms**:
```
Warning: NVENC encoder not found, falling back to software
```

**Solutions**:

1. **Check NVIDIA drivers**:
   ```bash
   nvidia-smi
   ```

2. **Update drivers**:
   - Download from [NVIDIA website](https://www.nvidia.com/Download/index.aspx)

3. **Check FFmpeg NVENC support**:
   ```bash
   ffmpeg -encoders | grep nvenc
   ```

4. **Verify GPU encoding capability**:
   - GeForce: GTX 1650+ (check [video encode specs](https://developer.nvidia.com/video-encode-and-decode-gpu-support-matrix))
   - Quadro/Tesla: Most models supported

### Issue: Intel QSV not working

**Symptoms**:
```
Warning: QSV encoder not found
```

**Solutions**:

1. **Install Media SDK**:
   ```bash
   # Ubuntu/Debian
   sudo apt install intel-media-va-driver-non-free libmfx1

   # Fedora
   sudo dnf install intel-media-driver
   ```

2. **Check VAAPI**:
   ```bash
   vainfo
   ```

3. **Verify FFmpeg build**:
   ```bash
   ffmpeg -version | grep qsv
   ```

---

## Debug Mode

### Enable Debug Logging

```bash
python -m video_renderer --debug --tui
```

Or set in config:
```json
{
  "core": {
    "log_level": "DEBUG"
  }
}
```

### Enable FFmpeg Debug Logs

```bash
# Set environment variable
export FFMPEG_LOG_LEVEL=debug  # Linux/macOS
set FFMPEG_LOG_LEVEL=debug     # Windows

# Or in Python
import os
os.environ['FFMPEG_LOG_LEVEL'] = 'debug'
```

### Create Debug Report

```bash
python -m video_renderer --debug-report > debug_report.txt
```

This will collect:
- System information
- FFmpeg version
- Configuration
- Recent log entries
- Hardware info

---

## Getting Help

### Before Asking for Help

1. **Check existing issues**:
   [GitHub Issues](https://github.com/ahmetcemkaraca/AutoVideo/issues)

2. **Search documentation**:
   [Documentation Index](../INDEX.md)

3. **Run diagnostics**:
   ```bash
   python -m video_renderer --health-check
   ```

### When Creating an Issue

Include:

1. **System Information**:
   ```bash
   python -m video_renderer --system-info
   ```

2. **Error Messages**:
   - Full error traceback
   - FFmpeg error output

3. **Configuration**:
   ```bash
   python -m video_renderer --show-config
   ```

4. **Steps to Reproduce**:
   - What you were trying to do
   - Commands you ran
   - Expected vs actual behavior

5. **Debug Report**:
   ```bash
   python -m video_renderer --debug-report
   ```

### Community Resources

- [GitHub Discussions](https://github.com/ahmetcemkaraca/AutoVideo/discussions)
- [Documentation](../INDEX.md)
- [Contributing Guide](../internal-docs/guides/contributing-guide.md)

---

## Error Codes Reference

| Error Code | Description | Solution |
|------------|-------------|----------|
| `E001` | FFmpeg not found | Install FFmpeg |
| `E002` | Video file not found | Check file path |
| `E003` | Invalid codec | Use valid codec |
| `E004` | Out of disk space | Clean up disk |
| `E005` | Out of memory | Close apps, reduce quality |
| `E006` | Authentication failed | Re-authenticate |
| `E007` | Upload quota exceeded | Wait or upgrade quota |
| `E008` | Permission denied | Check permissions |
| `E009` | Hardware encoder unavailable | Use software encoder |
| `E010` | Invalid configuration | Validate config |

---

**Last Updated**: 2025-02-06
**Version**: 1.0.0
