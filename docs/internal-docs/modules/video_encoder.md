# VideoEncoder Module

The VideoEncoder module (`video_renderer/video.py`) handles video encoding, normalization, and concatenation operations.

## Overview

VideoEncoder is responsible for:
- Video normalization (resolution, codec, FPS, pixel format)
- Hardware acceleration detection and fallback
- Video concatenation with repeat support
- Direct copy optimization for compatible videos
- GPU buffer optimization (high VRAM mode)

## Class Reference

### VideoEncoder

```python
class VideoEncoder:
    """Handles video encoding and processing operations."""

    def __init__(
        self,
        runner: FFmpegRunner,
        codec_config: CodecConfig,
        color_space: str = COLOR_BT709,
        width: int = 1920,
        height: int = 1080,
        fps: int = 60,
        high_vram: bool = False
    ):
        """
        Initialize VideoEncoder.

        Args:
            runner: FFmpegRunner instance for executing FFmpeg commands
            codec_config: Codec configuration (e.g., CODEC_H264)
            color_space: Color space (COLOR_BT709, COLOR_BT2020)
            width: Target width in pixels
            height: Target height in pixels
            fps: Target frames per second
            high_vram: Enable high VRAM optimizations
        """
```

## Key Methods

### check_compatibility

```python
def check_compatibility(self, source: Path) -> Tuple[bool, str]:
    """
    Check if source video is compatible with target settings.

    Args:
        source: Path to source video file

    Returns:
        Tuple of (is_compatible, reason)
        - is_compatible: True if video can be used directly
        - reason: Explanation if not compatible
    """
```

Checks:
- Resolution matches target (1920x1080)
- Codec matches target codec
- FPS matches target (60 fps)
- Pixel format is yuv420p

### normalize_video

```python
def normalize_video(
    self,
    source: Path,
    output: Path,
    progress_callback: Optional[Callable[[FFmpegProgress], None]] = None
) -> Path:
    """
    Normalize video to target settings.

    Args:
        source: Path to source video file
        output: Path for normalized output
        progress_callback: Optional callback for progress updates

    Returns:
        Path to normalized video file

    Raises:
        VideoProcessingError: If encoding fails
    """
```

Features:
- Automatic hardware acceleration (NVENC, QSV, VAAPI)
- GPU fallback to software encoding
- Direct copy optimization for compatible videos
- Progress tracking via callback

### concat_videos

```python
def concat_videos(
    self,
    intro: Path,
    loop: Path,
    output: Path,
    duration: float,
    progress_callback: Optional[Callable[[str, float], None]] = None
) -> Path:
    """
    Concatenate intro and loop videos to target duration.

    Args:
        intro: Path to intro video
        loop: Path to loop video
        output: Path for output video
        duration: Target duration in seconds
        progress_callback: Optional callback for progress

    Returns:
        Path to concatenated video file
    """
```

Process:
1. Normalize intro video
2. Normalize loop video
3. Calculate repeat count for loop
4. Concatenate intro + (loop × repeat)
5. Return path to output

### get_codec_family

```python
def get_codec_family(self, codec_name: str) -> str:
    """
    Get codec family from codec name.

    Args:
        codec_name: FFmpeg codec name (e.g., 'h264', 'libx265')

    Returns:
        Codec family ('h264', 'hevc', 'av1', or 'unknown')
    """
```

## Configuration

### Codec Configurations

```python
# Available codecs
CODEC_H264 = CodecConfig(
    name="H.264",
    encoder="libx264",
    hw_encoders=["h264_nvenc", "h264_qsv", "h264_vaapi"],
    preset="medium",
    crf=23
)

CODEC_H265 = CodecConfig(
    name="H.265/HEVC",
    encoder="libx265",
    hw_encoders=["hevc_nvenc", "hevc_qsv", "hevc_vaapi"],
    preset="medium",
    crf=28
)

CODEC_AV1 = CodecConfig(
    name="AV1",
    encoder="libsvtav1",
    hw_encoders=["av1_nvenc"],
    preset="8",
    crf=35
)
```

### Color Spaces

```python
COLOR_BT709 = "bt709"    # Standard HD
COLOR_BT2020 = "bt2020"  # HDR/UHD
```

## Hardware Acceleration

### Detection Priority

1. **NVENC** (NVIDIA): h264_nvenc, hevc_nvenc, av1_nvenc
2. **QSV** (Intel): h264_qsv, hevc_qsv
3. **VAAPI** (Linux): h264_vaapi, hevc_vaapi
4. **Software**: libx264, libx265, libsvtav1

### GPU Fallback

```python
# Automatic fallback when GPU encoding fails
try:
    # Try GPU encoding
    self._encode_with_gpu(source, output)
except Exception:
    # Fall back to software
    self._encode_with_cpu(source, output)
```

## High VRAM Mode

When `high_vram=True`, enables enhanced GPU settings:

| Setting | Standard | High VRAM |
|---------|----------|-----------|
| NVENC Surfaces | 64 | 128 |
| Lookahead Frames | 32 | 48 |
| Extra HW Frames | 8 | 16 |
| Decode Surfaces | 16 | 32 |

## Usage Examples

### Basic Usage

```python
from video_renderer.ffmpeg import FFmpegRunner
from video_renderer.video import VideoEncoder
from video_renderer.config import CODEC_H264, COLOR_BT709

runner = FFmpegRunner()
encoder = VideoEncoder(runner, CODEC_H264, COLOR_BT709)

# Check compatibility
is_compatible, reason = encoder.check_compatibility(Path("video.mp4"))
print(f"Compatible: {is_compatible}, Reason: {reason}")

# Normalize video
output = encoder.normalize_video(
    Path("input.mp4"),
    Path("output.mp4")
)

# Concat videos
final = encoder.concat_videos(
    Path("intro.mp4"),
    Path("loop.mp4"),
    Path("final.mp4"),
    duration=36000  # 10 hours
)
```

### With Progress Callback

```python
def on_progress(progress: FFmpegProgress):
    print(f"Progress: {progress.percent:.1f}%")

encoder.normalize_video(
    Path("input.mp4"),
    Path("output.mp4"),
    progress_callback=on_progress
)
```

### High VRAM Mode

```python
encoder = VideoEncoder(
    runner,
    CODEC_H265,
    COLOR_BT709,
    high_vram=True  # Enable GPU optimizations
)
```

## Error Handling

```python
from video_renderer.exceptions import VideoProcessingError

try:
    encoder.normalize_video(source, output)
except VideoProcessingError as e:
    print(f"Video processing failed: {e}")
```

## See Also

- [FFmpegRunner](ffmpeg_runner.md) - FFmpeg execution
- [AudioProcessor](audio_processor.md) - Audio processing
- [Configuration](../guides/configuration.md) - Configuration options
