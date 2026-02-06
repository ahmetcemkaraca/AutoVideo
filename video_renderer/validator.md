# Video Validator Module Documentation

## Overview

The `video_renderer.validator` module provides comprehensive video validation functionality for the AutoVideo project. It includes pre-render validation, post-render validation, and general video file validation using ffprobe.

## Components

### 1. Validation Result Structures

#### `ValidationSeverity` (Enum)
Severity levels for validation issues:
- `INFO` - Informational messages
- `WARNING` - Warning messages that don't prevent operation
- `ERROR` - Error messages that indicate problems
- `CRITICAL` - Critical errors that prevent operation

#### `ValidationIssue` (Dataclass)
Represents a single validation issue with bilingual support:
```python
@dataclass
class ValidationIssue:
    category: str              # e.g., "video", "audio", "disk"
    severity: ValidationSeverity
    message: str               # Primary message
    message_en: Optional[str]  # English message
    message_tr: Optional[str]  # Turkish message
    details: Optional[str]     # Additional details
    suggestion: Optional[str]  # Suggested fix
    field: Optional[str]       # Field name for structured validation
    context: Optional[Dict[str, Any]]  # Additional context
```

#### `ValidationResult` (Dataclass)
Complete validation result with bilingual support:
```python
@dataclass
class ValidationResult:
    valid: bool                           # Whether validation passed
    stage: Literal["pre_render", "post_render"]
    issues: List[ValidationIssue]         # All validation issues
    metadata: Dict[str, Any]              # Additional metadata
    duration_seconds: float               # Actual video duration
    file_size_bytes: int                  # Video file size
    video_info: Dict[str, Any]            # Extracted video information

    @property
    def errors(self) -> List[ValidationIssue]:  # ERROR and CRITICAL issues

    @property
    def warnings(self) -> List[ValidationIssue]:  # WARNING issues

    @property
    def info(self) -> List[ValidationIssue]:     # INFO issues
```

#### `VideoMetadata` (Dataclass)
Complete video metadata extracted by ffprobe:
```python
@dataclass
class VideoMetadata:
    codec: str                      # Video codec name
    width: int                      # Video width in pixels
    height: int                     # Video height in pixels
    fps: Fraction                   # Frame rate
    duration: float                 # Duration in seconds
    pix_fmt: str                    # Pixel format
    color_space: Optional[str]       # Color space
    color_primaries: Optional[str]   # Color primaries
    color_transfer: Optional[str]    # Color transfer
    bitrate: Optional[int]           # Video bitrate in bps
    has_audio: bool                  # Whether video has audio
    audio_codec: Optional[str]       # Audio codec name
    audio_channels: Optional[int]    # Number of audio channels
    audio_sample_rate: Optional[int] # Audio sample rate in Hz
    profile: Optional[str]           # Codec profile
    level: Optional[str]             # Codec level
    file_size: int                   # File size in bytes
```

### 2. VideoValidator Class

Comprehensive video validation using ffprobe.

#### Methods

- `is_ffprobe_available() -> bool`: Check if ffprobe is available (static method)
- `get_video_info(video_path: Path) -> VideoMetadata`: Extract complete video metadata
- `check_duration(video_path: Path, target_seconds: float) -> bool`: Check if duration matches target
- `check_codec(video_path: Path, expected_codec: str) -> bool`: Check if codec matches expected
- `check_resolution(video_path: Path, expected_resolution: Tuple[int, int]) -> bool`: Check resolution
- `check_fps(video_path: Path, expected_fps: Fraction) -> bool`: Check frame rate
- `check_audio(video_path: Path, has_audio: bool = True) -> bool`: Check audio presence
- `check_audio_tracks(video_path: Path, expected_count: int) -> bool`: Check audio track count
- `check_file_integrity(video_path: Path) -> bool`: Check file integrity
- `validate_output(video_path: Path, specs: Dict[str, Any]) -> ValidationResult`: Comprehensive validation

#### Example Usage
```python
from video_renderer.validator import VideoValidator
from pathlib import Path

validator = VideoValidator()

# Get video metadata
metadata = validator.get_video_info(Path("video.mp4"))
print(f"Codec: {metadata.codec}, Resolution: {metadata.width}x{metadata.height}")

# Validate against specifications
specs = {
    "duration_seconds": 3600,
    "width": 1920,
    "height": 1080,
    "fps": 60,
    "codec": "h264",
    "has_audio": True,
}
result = validator.validate_output(Path("output.mp4"), specs)
if result.valid:
    print("Validation passed!")
else:
    for error in result.errors:
        print(f"Error: {error.message}")
```

### 3. PreRenderValidator Class

Validates inputs before rendering starts.

#### Methods

- `validate_render_specs(intro_path, loop_path, single_path, tracks, target_duration, output_dir) -> ValidationResult`
  Validates complete render specification

#### Checks Performed

1. Video compatibility (intro/loop resolution, codec, FPS match)
2. Audio track validity and duration
3. Disk space availability
4. File accessibility

#### Example Usage
```python
from video_renderer.validator import PreRenderValidator
from pathlib import Path

validator = PreRenderValidator(target_width=1920, target_height=1080, target_fps=60)

result = validator.validate_render_specs(
    intro_path=Path("intro.mp4"),
    loop_path=Path("loop.mp4"),
    single_path=None,
    tracks=[Path("music1.mp3"), Path("music2.mp3")],
    target_duration=28800,  # 8 hours
    output_dir=Path(".")
)

if result.valid:
    print("Pre-render validation passed!")
else:
    for error in result.errors:
        print(f"[{error.category}] {error.message}")
        if error.suggestion:
            print(f"  Suggestion: {error.suggestion}")
```

### 4. PostRenderValidator Class

Validates output video after rendering completes.

#### Methods

- `validate_output(output_path, target_duration, target_specs) -> ValidationResult`
  Validates rendered output video

#### Checks Performed

1. Duration accuracy (±5 seconds from target)
2. Codec verification
3. Resolution and FPS
4. Audio quality and presence
5. File integrity

#### Example Usage
```python
from video_renderer.validator import PostRenderValidator
from pathlib import Path

validator = PostRenderValidator()

target_specs = {
    "codec": "h264",
    "width": 1920,
    "height": 1080,
    "fps": 60,
}

result = validator.validate_output(
    output_path=Path("final_output.mp4"),
    target_duration=28800,  # 8 hours
    target_specs=target_specs
)

if result.valid:
    print("Post-render validation passed!")
else:
    for error in result.errors:
        print(f"Error: {error.message}")
```

### 5. Convenience Functions

#### `validate_ffmpeg_available() -> ValidationResult`
Validate that FFmpeg and ffprobe are available.

#### `validate_before_render(intro_path, loop_path, single_path, tracks, target_duration, output_dir, **kwargs) -> ValidationResult`
Convenience function for pre-render validation.

#### `validate_after_render(output_path, target_duration, target_specs) -> ValidationResult`
Convenience function for post-render validation.

#### `quick_validate(video_path) -> Tuple[bool, str]`
Quick validation check for a single video file.

#### `export_validation_report(result, output_dir) -> Path`
Export validation report to JSON file.

### 6. Exception Classes

- `ValidationError`: Base exception for validation errors
- `FFprobeError`: Exception raised when ffprobe execution fails
- `FileCorruptedError`: Exception raised when video file is corrupted
- `DiskSpaceError`: Exception raised when insufficient disk space

## Usage Examples

### Complete Workflow Example

```python
from pathlib import Path
from video_renderer.validator import (
    PreRenderValidator,
    PostRenderValidator,
    export_validation_report
)

# 1. Pre-render validation
pre_validator = PreRenderValidator(
    target_width=1920,
    target_height=1080,
    target_fps=60
)

pre_result = pre_validator.validate_render_specs(
    intro_path=Path("intro.mp4"),
    loop_path=Path("loop.mp4"),
    single_path=None,
    tracks=[Path("music.mp3")],
    target_duration=36000,
    output_dir=Path(".")
)

if not pre_result.valid:
    print("Pre-render validation failed:")
    for error in pre_result.errors:
        print(f"  - {error.message}")
    exit(1)

# 2. Perform rendering...
# (Your rendering code here)

# 3. Post-render validation
post_validator = PostRenderValidator()

post_result = post_validator.validate_output(
    output_path=Path("final_video.mp4"),
    target_duration=36000,
    target_specs={
        "codec": "h264",
        "width": 1920,
        "height": 1080,
        "fps": 60,
        "has_audio": True,
    }
)

if not post_result.valid:
    print("Post-render validation failed:")
    for error in post_result.errors:
        print(f"  - {error.message}")
else:
    print("Validation successful!")

# 4. Export validation report
report_path = export_validation_report(post_result)
print(f"Validation report saved to: {report_path}")
```

## Bilingual Support

All validation messages support both English and Turkish:

```python
result.add_error(
    "video",
    "Video codec mismatch",  # English
    "Video codec uyusmazligi",  # Turkish
    suggestion="Re-encode with target codec"
)

# Get message in specific language
for issue in result.issues:
    print(issue.message_en)  # English
    print(issue.message_tr)  # Turkish
    print(issue.get_bilingual_message())  # Both: "EN: ... | TR: ..."
```

## Error Categories

- `video` - Video-related issues (codec, resolution, FPS)
- `audio` - Audio-related issues (codec, presence, quality)
- `disk` - Disk space issues
- `output` - Output file issues
- `tools` - FFmpeg/ffprobe availability
- `duration` - Duration-related issues
- `codec` - Codec-specific issues
- `resolution` - Resolution-related issues
- `fps` - Frame rate issues

## Best Practices

1. **Always validate before rendering** - Use `PreRenderValidator` to catch issues early
2. **Always validate after rendering** - Use `PostRenderValidator` to ensure output quality
3. **Handle bilingual messages** - Store both English and Turkish for user-facing messages
4. **Export validation reports** - Save reports for debugging and audit trails
5. **Check metadata** - Use the metadata in ValidationResult for detailed information
6. **Handle exceptions** - Catch specific exceptions (FFprobeError, FileCorruptedError, etc.)

## File Location

- **Module**: `C:\Users\ahmet\Desktop\Dev\Video\video_renderer\validator.py`
- **Documentation**: `C:\Users\ahmet\Desktop\Dev\Video\video_renderer\validator.md`
