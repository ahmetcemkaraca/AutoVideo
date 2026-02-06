# Video Validation System

## Overview

The AutoVideo validation system provides comprehensive checks for video and audio files throughout the rendering pipeline. It ensures that your source files are compatible, your output meets specifications, and your system is ready for production use.

**Key Features:**
- Pre-render validation of source files
- Post-render verification of output
- Bilingual error messages (English/Turkish)
- FFmpeg/ffprobe integration
- Disk space checking
- Audio-visual sync detection
- Production readiness checks

## Validation Checks

### Pre-Render Validation

Pre-render validation runs before any encoding begins, checking that your inputs are suitable for rendering.

#### Video File Checks

| Check | Description | Error Severity |
|-------|-------------|----------------|
| **File Existence** | Verifies video files exist at specified paths | ERROR |
| **Resolution Match** | Checks if intro and loop videos have matching resolution | WARNING |
| **FPS Match** | Verifies intro and loop have compatible frame rates | WARNING |
| **Codec Compatibility** | Checks if codec is supported (h264, hevc, av1, vp9) | INFO |
| **Pixel Format** | Validates pixel format (yuv420p, yuv420p10le, etc.) | WARNING |
| **File Size** | Ensures source files are not excessively large (>50GB) | ERROR |
| **Container Format** | Validates container format (.mp4, .mkv, .mov, .webm) | WARNING |

#### Audio File Checks

| Check | Description | Error Severity |
|-------|-------------|----------------|
| **File Existence** | Verifies audio files exist | ERROR |
| **Duration** | Checks if total audio duration meets target | WARNING |
| **Codec Support** | Validates audio codec compatibility | INFO |
| **Sample Rate** | Verifies sample rate (44.1kHz, 48kHz) | INFO |
| **Corruption Detection** | Detects corrupted or invalid audio files | ERROR |

#### System Checks

| Check | Description | Error Severity |
|-------|-------------|----------------|
| **FFmpeg Available** | Verifies FFmpeg is installed and accessible | CRITICAL |
| **ffprobe Available** | Verifies ffprobe is installed and accessible | CRITICAL |
| **Disk Space** | Checks sufficient disk space for rendering | ERROR/WARNING |
| **Python Dependencies** | Verifies required packages are installed | ERROR |
| **Directory Permissions** | Checks write access to output directories | ERROR |

### Post-Render Validation

Post-render validation verifies that the output meets your specifications.

#### Output Verification

| Check | Description | Tolerance |
|-------|-------------|-----------|
| **Duration Accuracy** | Compares actual duration to target | ±5 seconds |
| **Resolution Match** | Verifies output resolution | Exact match |
| **FPS Match** | Verifies output frame rate | ±0.1 FPS |
| **Codec Match** | Verifies output codec | Exact match |
| **Audio Presence** | Checks if audio stream exists | Required |
| **Audio-Visual Sync** | Detects AV sync issues | ±0.1 seconds |
| **File Integrity** | Verifies file is not corrupted | Binary check |
| **File Size** | Validates reasonable file size | 1-500 MB/min |

## Understanding Results

### Validation Result Structure

```python
ValidationResult {
    valid: bool                    # Overall pass/fail
    stage: "pre_render" | "post_render"
    issues: List[ValidationIssue]
    metadata: Dict[str, Any]
    duration_seconds: float
    file_size_bytes: int
    video_info: Dict[str, Any]
}
```

### Severity Levels

| Severity | Description | Action Required |
|----------|-------------|-----------------|
| **CRITICAL** | System cannot function | Must fix before proceeding |
| **ERROR** | Operation will fail | Must fix before proceeding |
| **WARNING** | Operation may succeed with issues | Review and address if needed |
| **INFO** | Informational message | No action required |

### Validation Issue Structure

```python
ValidationIssue {
    category: str              # "video", "audio", "disk", "tools"
    severity: str             # "error", "warning", "info", "critical"
    message: str              # Primary message
    message_en: str           # English message
    message_tr: str           # Turkish message
    details: str              # Additional details
    suggestion: str           # Recommended action
    field: str                # Related field name
    context: Dict[str, Any]   # Additional context
}
```

## Troubleshooting

### Common Validation Failures

#### File Not Found

**Error:** `Video dosyası bulunamadı: intro.mp4`

**Causes:**
- Incorrect file path
- File has been moved or deleted
- Case sensitivity in filename

**Solutions:**
1. Verify file exists: `ls -la path/to/intro.mp4`
2. Check file extension matches
3. Use absolute paths if relative paths fail
4. Check for typos in filename

#### Codec Not Supported

**Error:** `Desteklenmeyen codec: mpeg4`

**Causes:**
- Source file uses unsupported codec
- FFmpeg was compiled without codec support

**Solutions:**
1. Check source codec: `ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of default=noprint_wrappers=1:nokey=1 input.mp4`
2. Convert to supported codec: `ffmpeg -i input.mp4 -c:v libx264 output.mp4`
3. Reinstall FFmpeg with full codec support

#### Resolution Mismatch

**Warning:** `Cozunurluk uyusmazligi tespit edildi`

**Details:** `Intro: 1920x1080, Loop: 3840x2160`

**Impact:** Videos will be re-encoded to match target resolution

**Solutions:**
1. Accept re-encoding (automatic)
2. Pre-convert videos to matching resolution
3. Modify target resolution to match source

#### Insufficient Disk Space

**Error:** `Yetersiz disk alanı`

**Details:** `Gerekli: 15.2 GB, Mevcut: 8.5 GB`

**Solutions:**
1. Free up disk space
2. Change output directory to different drive
3. Reduce target duration
4. Use lower bitrate settings

#### FFprobe Timeout

**Error:** `ffprobe timeout on video.mp4`

**Causes:**
- Large video file (>4GB)
- Slow disk I/O
- Corrupted video file

**Solutions:**
1. Check file integrity: `ffmpeg -v error -i video.mp4 -f null - 2>&1`
2. Increase timeout in code
3. Copy file to faster storage
4. Repair corrupted video

#### Duration Mismatch

**Warning:** `Sure farki tespit edildi`

**Details:** `Hedef: 3600s, Gercek: 3598.5s, Fark: 1.5s`

**Impact:** Usually within acceptable tolerance (±5 seconds)

**Solutions:**
1. Accept if within tolerance (normal)
2. Adjust loop count if significant difference
3. Check source video duration accuracy

### Platform-Specific Issues

#### Windows

**Issue:** FFmpeg not found in PATH

**Solution:**
1. Download FFmpeg from https://ffmpeg.org/download.html
2. Extract to `C:\ffmpeg`
3. Add to PATH: `setx PATH "%PATH%;C:\ffmpeg\bin"`
4. Restart terminal

**Issue:** File path length limit (260 characters)

**Solution:**
- Use long path prefix: `\\?\C:\very\long\path...`
- Move files to shorter path
- Enable long path support in Windows 10+

#### macOS

**Issue:** FFprobe permission denied

**Solution:**
```bash
xcode-select --install
brew install ffmpeg
```

**Issue:** Gatekeeper blocking FFmpeg

**Solution:**
```bash
xattr -cr /usr/local/bin/ffmpeg
xattr -cr /usr/local/bin/ffprobe
```

#### Linux

**Issue:** Missing codec libraries

**Solution:**
```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg libavcodec-extra

# Fedora
sudo dnf install ffmpeg ffmpeg-compat

# Arch Linux
sudo pacman -S ffmpeg
```

**Issue:** Permission denied on output directory

**Solution:**
```bash
sudo chown $USER:$USER /path/to/output
chmod u+w /path/to/output
```

## Validation Settings and Options

### Configuring Validation Tolerances

```python
from video_renderer.validator import VideoValidator

# Custom tolerances
validator = VideoValidator(
    duration_tolerance=10.0,    # ±10 seconds for duration
    fps_tolerance=0.5,          # ±0.5 FPS
    bitrate_tolerance=0.15      # ±15% bitrate
)

# Use in validation
result = validator.validate_output(video_path, specs)
```

### Pre-Render Validation Settings

```python
from video_renderer.validator import PreRenderValidator

validator = PreRenderValidator(
    target_width=1920,
    target_height=1080,
    target_fps=60
)

result = validator.validate_render_specs(
    intro_path=Path("intro.mp4"),
    loop_path=Path("loop.mp4"),
    single_path=None,
    tracks=[Path("music1.mp3"), Path("music2.mp3")],
    target_duration=3600,
    output_dir=Path("output")
)
```

### Post-Render Validation Settings

```python
from video_renderer.validator import PostRenderValidator

validator = PostRenderValidator(
    duration_tolerance=5.0,
    fps_tolerance=0.1,
    bitrate_tolerance=0.1,
    sync_tolerance=0.1
)

result = validator.validate_output(
    output_path=Path("final.mp4"),
    target_duration=3600,
    target_specs={
        "codec": "h264",
        "width": 1920,
        "height": 1080,
        "fps": 60,
        "has_audio": True
    }
)
```

## Best Practices

### Before Rendering

1. **Check FFmpeg Installation**
   ```bash
   ffmpeg -version
   ffprobe -version
   ```

2. **Verify Source Files**
   ```python
   from video_renderer.validator import quick_validate
   from pathlib import Path

   for video in Path("videos").glob("*.mp4"):
       if quick_validate(video):
           print(f"✓ {video.name}")
       else:
           print(f"✗ {video.name}")
   ```

3. **Check Disk Space**
   ```python
   import shutil
   free_gb = shutil.disk_usage(".").free / (1024**3)
   print(f"Free space: {free_gb:.1f} GB")
   ```

4. **Validate Configuration**
   ```python
   from video_renderer.validator import validate_ffmpeg_available

   result = validate_ffmpeg_available()
   if not result.valid:
       print("Errors:", result.errors)
   ```

### During Rendering

1. **Monitor Progress**
   - Watch for validation warnings
   - Check disk space during long renders
   - Monitor audio track processing

2. **Handle Validation Failures**
   - Review error messages carefully
   - Check bilingual messages for clarity
   - Follow suggested fixes

### After Rendering

1. **Verify Output**
   ```python
   from video_renderer.validator import validate_after_render

   result = validate_after_render(
       output_path=Path("final_video.mp4"),
       target_duration=3600,
       target_specs={"codec": "h264", "width": 1920, "height": 1080}
   )

   if result.valid:
       print("✓ Output valid")
   else:
       print("✗ Errors found:")
       for error in result.errors:
           print(f"  - {error.message}")
   ```

2. **Export Validation Report**
   ```python
   from video_renderer.validator import export_validation_report

   report_path = export_validation_report(result, output_dir=Path("reports"))
   print(f"Report saved to: {report_path}")
   ```

## FAQ

### General Questions

**Q: Why does validation take so long?**

A: Validation uses ffprobe to extract metadata from video files. Large files or slow storage can increase processing time. Parallel validation can help with multiple files.

**Q: Can I skip validation?**

A: Pre-render validation can be skipped, but this is not recommended. Invalid inputs can cause rendering failures or corrupted outputs. Post-render validation is automatic.

**Q: What's the difference between ERROR and WARNING?**

A: ERRORS must be fixed before rendering can succeed. WARNINGS indicate potential issues that may not prevent rendering but could affect quality.

### Technical Questions

**Q: Which codecs are supported?**

A: Main video codecs: h264, hevc (h265), av1, vp9. Audio codecs: aac, mp3, opus, flac.

**Q: What pixel formats are accepted?**

A: Standard: yuv420p, yuvj420p. HDR/10-bit: yuv420p10le, yuv420p10.

**Q: How is FPS checked?**

A: FPS is compared as a fraction to handle common frame rates like 29.97 (30000/1001) and 23.976 (24000/1001).

**Q: What's the minimum disk space required?**

A: Minimum 1 GB free space. Recommended: 3x the total source file size for temporary files and output.

### Error Messages

**Q: What does "Video akisi bulunamadi" mean?**

A: "No video stream found" - The file doesn't contain a video track. This may be an audio-only file or corrupted video.

**Q: What does "Ses varligi uyusmazligi" mean?**

A: "Audio presence mismatch" - Expected audio but found none, or vice versa.

**Q: What does "Cozunurluk farkli" mean?**

A: "Resolution different" - Source video resolution doesn't match target. Video will be re-encoded.

## Integration Examples

### Basic Validation

```python
from pathlib import Path
from video_renderer.validator import (
    validate_before_render,
    validate_after_render,
    validate_ffmpeg_available
)

# Check tools
tools_result = validate_ffmpeg_available()
if not tools_result.valid:
    print("❌ FFmpeg not available")
    exit(1)

# Validate before rendering
pre_result = validate_before_render(
    intro_path=Path("intro.mp4"),
    loop_path=Path("loop.mp4"),
    single_path=None,
    tracks=[Path("music.mp3")],
    target_duration=3600,
    output_dir=Path("output")
)

if not pre_result.valid:
    print("❌ Pre-render validation failed:")
    for error in pre_result.errors:
        print(f"  {error.message}")
    exit(1)

# ... perform rendering ...

# Validate after rendering
post_result = validate_after_render(
    output_path=Path("output/final.mp4"),
    target_duration=3600,
    target_specs={
        "codec": "h264",
        "width": 1920,
        "height": 1080,
        "fps": 60
    }
)

if post_result.valid:
    print("✓ Output validation passed")
else:
    print("⚠ Post-render validation warnings:")
    for warning in post_result.warnings:
        print(f"  {warning.message}")
```

### Batch Validation

```python
from pathlib import Path
from video_renderer.validator import VideoValidator

validator = VideoValidator(duration_tolerance=5.0)

video_files = list(Path("videos").glob("*.mp4"))

for video_path in video_files:
    specs = {
        "duration_seconds": 3600,
        "width": 1920,
        "height": 1080,
        "fps": 60,
        "codec": "h264",
        "has_audio": True
    }

    result = validator.validate_output(video_path, specs)

    status = "✓" if result.valid else "✗"
    print(f"{status} {video_path.name}")

    if not result.valid:
        for error in result.errors:
            print(f"  ERROR: {error.message}")
```

### Custom Validation Rules

```python
from video_renderer.validator import VideoValidator, ValidationResult

class CustomValidator(VideoValidator):
    def validate_output(self, video_path, specs):
        result = super().validate_output(video_path, specs)

        # Add custom check: minimum bitrate
        metadata = self.get_video_info(video_path)
        if metadata.bitrate and metadata.bitrate < 2_000_000:  # 2 Mbps
            result.add_warning(
                "video",
                "Low bitrate detected",
                "Düşük bitrate algılandı",
                details=f"Bitrate: {metadata.bitrate / 1_000_000:.2f} Mbps",
                suggestion="Use at least 2 Mbps for 1080p"
            )

        return result

validator = CustomValidator()
result = validator.validate_output(Path("video.mp4"), specs)
```

## Additional Resources

- **Validator Module API**: See `docs/internal-docs/validation/architecture.md`
- **Troubleshooting Guide**: See `docs/internal-docs/validation/troubleshooting.md`
- **FFmpeg Documentation**: https://ffmpeg.org/documentation.html
- **ffprobe Documentation**: https://ffmpeg.org/ffprobe.html

## Error Message Reference

### English Messages

| Message | Cause | Solution |
|---------|-------|----------|
| Output file not found | Render didn't complete | Check render logs |
| Duration mismatch | Actual ≠ target duration | Adjust loop count or target |
| Resolution mismatch | Output has wrong resolution | Check encoder settings |
| Codec mismatch | Wrong codec used | Verify codec config |
| No video stream found | File has no video track | Use valid video file |
| Audio presence mismatch | Missing or unexpected audio | Check audio settings |
| Insufficient disk space | Not enough free space | Free disk space |
| FFmpeg not found | FFmpeg not installed | Install FFmpeg |
| File integrity check failed | Output is corrupted | Re-render video |

### Turkish Messages

| Mesaj | Neden | Çözüm |
|-------|-------|-------|
| Çıktı dosyası bulunamadı | Render tamamlanmadı | Render loglarını kontrol edin |
| Süre farkı tespit edildi | Gerçek ≠ hedef süre | Loop sayısını ayarlayın |
| Çözünürlük farklı | Yanlış çözünürlük | Encoder ayarlarını kontrol edin |
| Codec uyusmazligi | Yanlış codec kullanıldı | Codec yapılandırmasını doğrulayın |
| Video akisi bulunamadi | Dosyada video akışı yok | Geçerli video dosyası kullanın |
| Ses varligi uyusmazligi | Eksik veya beklenmeyen ses | Ses ayarlarını kontrol edin |
| Yetersiz disk alanı | Yeterli boş alan yok | Disk alanı açın |
| FFmpeg bulunamadı | FFmpeg kurulu değil | FFmpeg'i yükleyin |
| Dosya bütünlüğü kontrolü başarısız | Çıktı bozuk | Video'yu yeniden render edin |

---

**Last Updated:** 2026-02-06

**Version:** 1.0

**For Developers:** See `docs/internal-docs/validation/architecture.md` for implementation details.
