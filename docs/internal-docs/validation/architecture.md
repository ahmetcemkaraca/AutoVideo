# Validation Module Architecture

## Overview

The validation system in AutoVideo is distributed across multiple modules, each handling specific aspects of validation:

1. **Video Validation** (`video_renderer/validator.py`) - Core video validation with ffprobe
2. **Audio Validation** (`video_renderer/audio.py`) - Audio file processing and validation
3. **Config Validation** (`config/validation.py`) - JSON Schema-based config validation
4. **Pipeline Validation** (`VideoAutomation/automation/validation.py`) - Production readiness checks

## Module Architecture

### Video Validation (`video_renderer/validator.py`)

#### VideoValidator Class

The `VideoValidator` class provides comprehensive video validation using ffprobe.

**Key Features:**
- **Fast metadata extraction**: Uses ffprobe for efficient video analysis
- **Codec compatibility checking**: Validates codec support and aliases
- **Duration accuracy validation**: Checks duration within configurable tolerance
- **Audio-visual sync detection**: Compares stream durations for sync issues
- **File integrity verification**: Basic sanity checks on video properties

**Class Definition:**
```python
class VideoValidator:
    """Comprehensive video validation using ffprobe."""

    # Default tolerances for validation
    DEFAULT_DURATION_TOLERANCE_SEC = 5.0
    DEFAULT_FPS_TOLERANCE = 0.1
    DEFAULT_BITRATE_TOLERANCE = 0.1  # 10%

    def __init__(
        self,
        duration_tolerance: float = DEFAULT_DURATION_TOLERANCE_SEC,
        fps_tolerance: float = DEFAULT_FPS_TOLERANCE,
        bitrate_tolerance: float = DEFAULT_BITRATE_TOLERANCE,
    ):
        """Initialize VideoValidator with custom tolerances."""
```

**Methods:**

##### get_video_info()

Extract complete video metadata using ffprobe.

```python
def get_video_info(self, video_path: Path) -> VideoMetadata:
    """
    Extract complete video metadata using ffprobe.

    Args:
        video_path: Path to video file

    Returns:
        VideoMetadata object with all extracted information

    Raises:
        FFprobeError: If ffprobe execution fails
        FileCorruptedError: If video file is corrupted
    """
```

**VideoMetadata Structure:**
```python
@dataclass
class VideoMetadata:
    """Complete video metadata extracted by ffprobe."""
    codec: str
    width: int
    height: int
    fps: Fraction
    duration: float
    pix_fmt: str
    color_space: Optional[str] = None
    color_primaries: Optional[str] = None
    color_transfer: Optional[str] = None
    bitrate: Optional[int] = None
    has_audio: bool = False
    audio_codec: Optional[str] = None
    audio_channels: Optional[int] = None
    audio_sample_rate: Optional[int] = None
    profile: Optional[str] = None
    level: Optional[str] = None
    file_size: int = 0
```

##### check_duration()

Check if video duration matches target within tolerance.

```python
def check_duration(self, video_path: Path, target_seconds: float) -> bool:
    """
    Check if video duration matches target within tolerance.

    Args:
        video_path: Path to video file
        target_seconds: Target duration in seconds

    Returns:
        True if duration is within tolerance
    """
```

##### check_codec()

Check if video codec matches expected codec with alias support.

```python
def check_codec(self, video_path: Path, expected_codec: str) -> bool:
    """
    Check if video codec matches expected codec.

    Args:
        video_path: Path to video file
        expected_codec: Expected codec name (e.g., 'h264', 'hevc', 'av1')

    Returns:
        True if codec matches (including aliases)
    """
```

**Codec Aliases:**
```python
codec_mapping = {
    "h264": ["h264", "avc", "libx264"],
    "hevc": ["hevc", "h265", "libx265"],
    "av1": ["av1", "libsvtav1"],
    "vp9": ["vp9", "libvpx-vp9"],
    "vp8": ["vp8", "libvpx"],
}
```

##### validate_output()

Comprehensive post-render validation against specifications.

```python
def validate_output(
    self,
    video_path: Path,
    specs: Dict[str, Any]
) -> ValidationResult:
    """
    Comprehensive post-render validation against specifications.

    Validates:
    - File exists and is readable
    - Duration matches target (within tolerance)
    - Resolution matches target
    - FPS matches target (within tolerance)
    - Codec matches expected codec
    - Audio is present if required
    - Audio track count matches expected
    - File integrity

    Args:
        video_path: Path to rendered video
        specs: Dictionary with validation specifications

    Returns:
        ValidationResult with detailed status
    """
```

**Validation Specifications:**
```python
specs = {
    "duration_seconds": 3600,    # Target duration
    "width": 1920,                # Target width
    "height": 1080,               # Target height
    "fps": 60,                    # Target FPS
    "codec": "h264",              # Expected codec
    "has_audio": True,            # Whether audio should be present
    "audio_tracks": 1,            # Expected number of audio tracks
    "min_bitrate": 2_000_000,     # Minimum bitrate (optional)
    "max_bitrate": 10_000_000,    # Maximum bitrate (optional)
}
```

#### PreRenderValidator Class

Validates inputs before rendering starts.

```python
class PreRenderValidator:
    """Validates inputs before rendering starts."""

    DISK_SPACE_MULTIPLIER = 3.0   # Need 3x source file size
    MIN_FREE_SPACE = 1 * 1024**3   # Minimum 1 GB free

    def __init__(self, target_width: int = 1920, target_height: int = 1080, target_fps: int = 60):
        """Initialize PreRenderValidator."""
```

**Methods:**

##### validate_render_specs()

Validate complete render specification.

```python
def validate_render_specs(
    self,
    intro_path: Optional[Path],
    loop_path: Optional[Path],
    single_path: Optional[Path],
    tracks: List[Path],
    target_duration: int,
    output_dir: Path,
) -> ValidationResult:
    """
    Validate complete render specification.

    Args:
        intro_path: Optional intro video path
        loop_path: Optional loop video path
        single_path: Optional single video path (for single mode)
        tracks: List of audio track paths
        target_duration: Target duration in seconds
        output_dir: Output directory path

    Returns:
        ValidationResult with all issues found
    """
```

**Validation Steps:**
1. Determine render mode (single vs intro_loop)
2. Validate video file(s) for mode
3. Validate audio tracks
4. Validate disk space

#### PostRenderValidator Class

Enhanced post-render validation with audio-visual sync checking.

```python
class PostRenderValidator(VideoValidator):
    """Enhanced post-render validation with audio-visual sync checking."""

    DURATION_TOLERANCE = 5        # Duration tolerance in seconds
    MIN_AUDIO_BITRATE = 128       # Minimum expected audio bitrate (kbps)
    SYNC_TOLERANCE = 0.1          # Audio-visual sync tolerance in seconds

    def __init__(
        self,
        duration_tolerance: float = 5.0,
        fps_tolerance: float = 0.1,
        bitrate_tolerance: float = 0.1,
        sync_tolerance: float = 0.1,
    ):
        """Initialize PostRenderValidator."""
```

**Methods:**

##### validate_output()

Validate rendered output video.

```python
def validate_output(
    self,
    output_path: Path,
    target_duration: int,
    target_specs: Optional[Dict[str, Any]] = None,
) -> ValidationResult:
    """
    Validate rendered output video.

    Args:
        output_path: Path to rendered output video
        target_duration: Target duration in seconds
        target_specs: Optional dict with expected codec, resolution, fps

    Returns:
        ValidationResult with all issues found
    """
```

##### check_av_sync()

Check for audio-visual sync issues by comparing stream durations.

```python
def check_av_sync(self, video_path: Path) -> bool:
    """
    Check for audio-visual sync issues by comparing stream durations.

    Args:
        video_path: Path to video file

    Returns:
        True if sync appears OK (durations within tolerance)
    """
```

### Audio Validation (`video_renderer/audio.py`)

#### AudioProcessor Class

The `AudioProcessor` class handles audio validation and conversion.

**Key Features:**
- **Parallel validation**: Validate multiple tracks concurrently
- **Caching**: Avoid re-processing unchanged files
- **Metadata preservation**: Extract and restore metadata
- **Channel preservation**: Detect and preserve mono/stereo

**Validation Methods:**

##### validate_and_convert_track()

Validate and convert a single audio track.

```python
def validate_and_convert_track(
    self,
    track: Path,
    use_cache: bool = True,
    preserve_metadata: bool = True
) -> Tuple[Path, bool, str]:
    """
    Validate and convert a single audio track.

    Returns:
        Tuple of (output_path, success, error_message)
    """
```

**Cache Strategy:**
```python
# Cache key using size + mtime for invalidation
stat = track.stat()
cache_key = f"{track.name}_{stat.st_size}_{stat.st_mtime}"
output = self.tmp_dir / f"validated_{safe_name}.{self.INTERMEDIATE_FORMAT}"

# Check cache
if use_cache and cache_key in self._validated_cache and output.exists():
    return output, True, ""
```

##### validate_tracks()

Validate multiple audio tracks with optional parallel processing.

```python
def validate_tracks(
    self,
    tracks: List[Path],
    parallel: bool = True,
    progress_callback: Optional[Callable] = None
) -> Tuple[List[Path], List[Tuple[Path, str]]]:
    """
    Validate multiple audio tracks.

    Returns:
        Tuple of (valid_tracks, invalid_tracks_with_errors)
    """
```

**Parallel Validation:**
```python
def _validate_tracks_parallel(self, tracks: List[Path], progress_callback: Optional[Callable]):
    """Parallel track validation using ThreadPoolExecutor."""
    with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
        futures = {
            executor.submit(self.validate_and_convert_track, track): track
            for track in tracks
        }
        for future in as_completed(futures):
            output, success, error = future.result()
            # Process results
```

### Config Validation (`config/validation.py`)

#### ValidationResult Dataclass

```python
@dataclass
class ValidationResult:
    """Validation sonucu."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]

    def add_error(self, message: str):
        """Hata ekle."""
        self.errors.append(message)
        self.is_valid = False

    def add_warning(self, message: str):
        """Uyarı ekle."""
        self.warnings.append(message)

    def merge(self, other: 'ValidationResult'):
        """Başka bir sonucu birleştir."""
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.is_valid = self.is_valid and other.is_valid
```

#### ConfigValidator Class

```python
class ConfigValidator:
    """Pipeline configuration validator."""

    def validate(self, config: Any) -> ValidationResult:
        """Config'i validate et."""
        self.result = ValidationResult(is_valid=True, errors=[], warnings=[])

        self._validate_directories(config)
        self._validate_video_settings(config)
        self._validate_youtube_config(config)
        self._validate_pipeline_settings(config)

        return self.result
```

**Validation Categories:**

1. **Directory Validation**
   - Check work_dir exists
   - Check music_dir exists and contains MP3 files
   - Verify output_dir is specified

2. **Video Settings Validation**
   - File existence (intro_video, loop_video)
   - File format compatibility
   - Duration format (HH:MM:SS or MM:SS)
   - Codec validity (av1, h264, h265, vp9)

3. **YouTube Config Validation**
   - Client secrets file existence and validity
   - Privacy status (public, private, unlisted)
   - Category ID (1-999)
   - Title template variables
   - Tag count and length limits

4. **Pipeline Settings Validation**
   - Delay between videos (0-86400 seconds)
   - Styles list (at least 2 recommended)
   - Genres list (at least 2 recommended)

#### JSON Schema Validation

```python
RENDER_CONFIG_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Video Renderer Configuration",
    "type": "object",
    "properties": {
        "work_dir": {"type": "string"},
        "width": {"type": "integer", "minimum": 1},
        "height": {"type": "integer", "minimum": 1},
        "fps": {"type": "integer", "enum": [24, 25, 30, 50, 60]},
        "codec": {"type": "string", "enum": ["h264", "h265", "vp9", "av1"]},
        "duration_seconds": {"type": "integer", "minimum": 0},
    },
}

def validate_config(data: Dict[str, Any], schema_name: str) -> bool:
    """Validate config against JSON schema."""
    import jsonschema
    from jsonschema import validate, ValidationError

    schema = schemas.get(schema_name)
    validate(instance=data, schema=schema)
    return True
```

### Pipeline Validation (`VideoAutomation/automation/validation.py`)

#### ProductionReadinessChecker Class

```python
class ProductionReadinessChecker:
    """Production readiness kontrolü."""

    def check(self, config: Any) -> ValidationResult:
        """Prodüksiyon readiness kontrolü yap."""
        self.result = ValidationResult(is_valid=True, errors=[], warnings=[])

        # Önce basic validation
        validator = ConfigValidator()
        basic_result = validator.validate(config)
        self.result.merge(basic_result)

        # Production-specific checks
        self._check_dependencies()
        self._check_disk_space(config)
        self._check_ffmpeg()
        self._check_credentials(config)

        return self.result
```

**Production Checks:**

1. **Dependencies Check**
   ```python
   def _check_dependencies(self):
       required_packages = [
           ("googleapiclient", "google-api-python-client"),
           ("google_auth_oauthlib", "google-auth-oauthlib"),
           ("rich", "rich"),
       ]
       for package_name, pip_name in required_packages:
           try:
               __import__(package_name)
           except ImportError:
               self.result.add_error(f"Package kurulu değil: {pip_name}")
   ```

2. **Disk Space Check**
   ```python
   def _check_disk_space(self, config):
       work_dir = Path(config.work_dir) if config.work_dir else Path.cwd()
       total, used, free = shutil.disk_usage(work_dir)

       required_gb = 10
       free_gb = free / (1024 ** 3)

       if free_gb < required_gb:
           self.result.add_warning(
               f"Disk alanı düşük: {free_gb:.1f} GB (en az {required_gb} GB önerilir)"
           )
   ```

3. **FFmpeg Check**
   ```python
   def _check_ffmpeg(self):
       try:
           result = subprocess.run(
               ["ffmpeg", "-version"],
               capture_output=True,
               text=True,
               timeout=5
           )
           if result.returncode != 0:
               self.result.add_error("FFmpeg çalışmıyor")
       except FileNotFoundError:
           self.result.add_error("FFmpeg bulunamadı")
   ```

4. **Credentials Check**
   ```python
   def _check_credentials(self, config):
       if config.youtube and config.youtube.client_secrets_file:
           secrets_path = Path(config.youtube.client_secrets_file)

           if secrets_path.exists():
               try:
                   with open(secrets_path, 'r') as f:
                       data = json.load(f)

                   if "installed" not in data and "web" not in data:
                       self.result.add_error("client_secrets.json formatı geçersiz")
               except json.JSONDecodeError:
                   self.result.add_error("client_secrets.json geçersiz JSON")
   ```

## API Reference

### VideoValidator

#### is_ffprobe_available()

Static method to check if ffprobe is available.

```python
@staticmethod
def is_ffprobe_available() -> bool:
    """
    Check if ffprobe is available without raising exception.

    Returns:
        True if ffprobe is found in PATH
    """
```

#### check_file_integrity()

Check video file integrity by attempting to read metadata.

```python
def check_file_integrity(self, video_path: Path) -> bool:
    """
    Check video file integrity by attempting to read metadata.

    Args:
        video_path: Path to video file

    Returns:
        True if file appears to be intact
    """
```

### PreRenderValidator

#### _validate_single_video()

Validate single video for single mode rendering.

```python
def _validate_single_video(self, video_path: Path, result: ValidationResult) -> None:
    """Validate single video for single mode rendering."""
```

#### _validate_intro_loop_pair()

Validate intro and loop video pair for compatibility.

```python
def _validate_intro_loop_pair(
    self,
    intro_path: Path,
    loop_path: Path,
    result: ValidationResult
) -> None:
    """Validate intro and loop video pair for compatibility."""
```

#### _validate_audio_tracks()

Validate audio tracks.

```python
def _validate_audio_tracks(
    self,
    tracks: List[Path],
    target_duration: int,
    result: ValidationResult
) -> None:
    """Validate audio tracks."""
```

#### _validate_disk_space()

Validate available disk space.

```python
def _validate_disk_space(
    self,
    primary_video: Optional[Path],
    secondary_video: Optional[Path],
    tracks: List[Path],
    target_duration: int,
    output_dir: Path,
    result: ValidationResult
) -> None:
    """Validate available disk space."""
```

### PostRenderValidator

#### validate_render()

Full post-render validation for both intro_loop and single modes.

```python
def validate_render(
    self,
    video_path: Path,
    specs: Dict[str, Any],
    mode: str = "intro_loop"
) -> ValidationResult:
    """
    Full post-render validation for both intro_loop and single modes.

    Args:
        video_path: Path to rendered video
        specs: Render specifications including duration, codec, resolution, etc.
        mode: Render mode ("intro_loop" or "single")

    Returns:
        ValidationResult with complete validation status
    """
```

## Integration Points

### 1. Render Pipeline Integration

**Location:** `video_renderer/screens/render.py`

```python
# Before rendering, validate video compatibility
from video_renderer.validator import validate_before_render

result = validate_before_render(
    intro_path=Path("intro.mp4"),
    loop_path=Path("loop.mp4"),
    single_path=None,
    tracks=[Path("music.mp3")],
    target_duration=3600,
    output_dir=Path("output")
)

if not result.valid:
    print("Validation failed:")
    for error in result.errors:
        print(f"  - {error.message}")
    sys.exit(1)
```

### 2. Batch Processing Integration

**Location:** `video_renderer/batch.py`

```python
# Validate all jobs before starting batch
for job in queue.jobs:
    validator = PreRenderValidator()

    result = validator.validate_render_specs(
        intro_path=job.intro_path,
        loop_path=job.loop_path,
        single_path=job.single_path,
        tracks=job.tracks,
        target_duration=job.target_duration,
        output_dir=job.output_dir
    )

    if not result.valid:
        job.add_warnings(result.warnings)
    if result.errors:
        job.add_errors(result.errors)
```

### 3. Automation Pipeline Integration

**Location:** `VideoAutomation/automation/pipeline.py`

```python
# Validate configuration before starting automation
from VideoAutomation.automation.validation import check_production_readiness

result = check_production_readiness(config)
if not result.is_valid:
    print("Configuration errors:")
    for error in result.errors:
        print(f"  - {error}")
    sys.exit(1)

print("Warnings:")
for warning in result.warnings:
    print(f"  - {warning}")
```

### 4. Audio Processing Integration

**Location:** `video_renderer/audio.py`

```python
# Validate tracks before looping
processor = AudioProcessor(runner, tmp_dir)

valid_tracks, invalid = processor.validate_tracks(
    tracks, parallel=True, progress_callback=progress_cb
)

if invalid:
    print(f"Warning: {len(invalid)} tracks failed validation:")
    for track, error in invalid:
        print(f"  - {track.name}: {error}")

# Loop only valid tracks
audio_path = processor.loop_audio(valid_tracks, target_duration, progress_callback)
```

## Extending Validation Checks

### Adding a New Video Validation Check

To add a new validation check for videos:

1. **Add the check method to `VideoValidator`:**

```python
def validate_output(self, video_path: Path, specs: Dict[str, Any]) -> ValidationResult:
    # ... existing checks ...

    # NEW: Check color space
    if "color_space" in specs:
        metadata = self.get_video_info(video_path)
        if metadata.color_space and metadata.color_space != specs["color_space"]:
            result.add_warning(
                "video",
                f"Color space mismatch: {metadata.color_space}",
                f"Renk uzayı uyumsuz: {metadata.color_space}",
                details=f"Expected: {specs['color_space']}",
                field="color_space"
            )

    return result
```

2. **Add helper method for detection:**

```python
def _get_color_space(self, video_path: Path) -> Optional[str]:
    """Detect color space from video file."""
    metadata = self.get_video_info(video_path)
    return metadata.color_space
```

### Adding a New Audio Validation Check

To add a new validation check for audio:

1. **Add the check to `validate_and_convert_track`:**

```python
def validate_and_convert_track(self, track: Path, ...) -> Tuple[Path, bool, str]:
    # ... existing code ...

    # NEW: Check bit depth
    bit_depth = self._get_bit_depth(track)
    if bit_depth and bit_depth < 16:
        return track, False, f"Bit depth too low: {bit_depth} (minimum 16)"

    # ... continue with conversion ...
```

2. **Add helper method for detection:**

```python
def _get_bit_depth(self, file_path: Path) -> Optional[int]:
    """Detect bit depth from audio file."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-show_streams", "-select_streams", "a",
        "-of", "json", str(file_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    if data.get("streams"):
        return int(data["streams"][0].get("bits_per_sample", 16))
    return None
```

### Adding a New Config Validation

To add a new configuration validation:

1. **Add validation method to `ConfigValidator`:**

```python
def _validate_video_settings(self, config):
    # ... existing validations ...

    # NEW: Validate bitrate settings
    if hasattr(config, 'video_bitrate'):
        bitrate = config.video_bitrate.upper()
        if not bitrate.endswith('M') and not bitrate.endswith('K'):
            self.result.add_error(f"Geçersiz bitrate formatı: {bitrate}")

    # NEW: Validate preset
    if hasattr(config, 'preset'):
        valid_presets = {"ultrafast", "superfast", "veryfast", "faster", "fast",
                        "medium", "slow", "slower", "veryslow"}
        if config.preset.lower() not in valid_presets:
            self.result.add_error(f"Geçersiz preset: {config.preset}")
```

## Performance Considerations

### Caching Strategy

**Video Compatibility Cache:**
- Key: `(file_path, encoder, width, height, fps)`
- Scope: Class-level (shared across instances)
- Invalidation: None (manual cache clearing required)

**Audio Validation Cache:**
- Key: `(filename, size, modification_time)`
- Scope: Instance-level (per AudioProcessor instance)
- Invalidation: Automatic when file changes

### Parallel Processing

**Audio Validation:**
- Default workers: `min(4, os.cpu_count())`
- Configurable via `max_workers` parameter
- Uses `ThreadPoolExecutor` for I/O-bound operations

**Recommendations:**
- Use parallel validation for batches of 10+ files
- Use sequential validation for small batches to avoid overhead
- Adjust worker count based on disk I/O performance

## Error Handling Strategy

### Validation Errors

Validation follows a fail-fast approach:

1. **Critical Errors** - Stop processing immediately
   - File not found
   - Invalid codec
   - Corrupted file

2. **Warnings** - Continue with notification
   - Non-standard format
   - Low disk space
   - Missing optional metadata

3. **Recoverable Errors** - Attempt recovery
   - GPU encoding failure → fallback to software
   - Timeout → retry with increased timeout
   - Minor corruption → ignore with `-err_detect ignore_err`

### Logging

All validation modules use Python's logging:

```python
logger = logging.getLogger(__name__)

logger.warning(f"Unknown codec encoder: {self.codec.encoder}")
logger.info(f"Schema saved to {schema_file}")
```

Configure logging level in application:
```python
logging.basicConfig(level=logging.INFO)
```

## Testing Validation

### Unit Testing

```python
import pytest
from video_renderer.validator import VideoValidator

def test_duration_validation():
    """Test duration validation."""
    validator = VideoValidator(duration_tolerance=5.0)

    # Test with valid duration
    assert validator.check_duration(Path("test.mp4"), 3600) == True

    # Test with invalid duration
    assert validator.check_duration(Path("test.mp4"), 100) == False
```

### Integration Testing

```python
def test_full_validation_pipeline():
    """Test validation in full pipeline."""
    validator = PreRenderValidator()

    result = validator.validate_render_specs(
        intro_path=Path("intro.mp4"),
        loop_path=Path("loop.mp4"),
        single_path=None,
        tracks=[Path("music.mp3")],
        target_duration=3600,
        output_dir=Path("output")
    )

    assert result.valid == True
    assert len(result.errors) == 0
```

## Data Structures

### ValidationIssue

```python
@dataclass
class ValidationIssue:
    """A single validation issue with bilingual support."""
    category: str                      # e.g., "video", "audio", "disk"
    severity: ValidationSeverity        # INFO, WARNING, ERROR, CRITICAL
    message: str                       # Primary message
    message_en: Optional[str]          # English message
    message_tr: Optional[str]          # Turkish message
    details: Optional[str]             # Additional details
    suggestion: Optional[str]          # How to fix
    field: Optional[str]               # Field name for structured validation
    context: Optional[Dict[str, Any]]  # Additional context
```

### ValidationResult

```python
@dataclass
class ValidationResult:
    """Complete validation result with bilingual support."""
    valid: bool                              # Overall validity status
    stage: Literal["pre_render", "post_render"]  # Validation stage
    issues: List[ValidationIssue]            # All issues found
    metadata: Dict[str, Any]                 # Additional metadata
    duration_seconds: float                  # Actual video duration
    file_size_bytes: int                     # Video file size
    video_info: Dict[str, Any]               # Extracted video information

    @property
    def errors(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL)]

    @property
    def warnings(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]

    @property
    def info(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.INFO]
```

### ValidationSeverity

```python
class ValidationSeverity(Enum):
    """Severity level for validation issues."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
```

## Convenience Functions

### validate_before_render()

Convenience function for pre-render validation.

```python
def validate_before_render(
    intro_path: Optional[Path],
    loop_path: Optional[Path],
    single_path: Optional[Path],
    tracks: List[Path],
    target_duration: int,
    output_dir: Path,
    **kwargs
) -> ValidationResult:
    """
    Convenience function for pre-render validation.

    Returns:
        ValidationResult with all validation issues
    """
```

### validate_after_render()

Convenience function for post-render validation.

```python
def validate_after_render(
    output_path: Path,
    target_duration: int,
    target_specs: Optional[Dict[str, Any]] = None,
) -> ValidationResult:
    """
    Convenience function for post-render validation.

    Returns:
        ValidationResult with all validation issues
    """
```

### export_validation_report()

Export validation report to JSON file.

```python
def export_validation_report(
    result: ValidationResult,
    output_dir: Optional[Path] = None,
) -> Path:
    """
    Export validation report to JSON file.

    Args:
        result: ValidationResult to export
        output_dir: Optional output directory (defaults to cwd/reports/)

    Returns:
        Path to the exported report file
    """
```

### validate_video_file()

Convenience function for quick video validation.

```python
def validate_video_file(
    video_path: Path,
    expected_duration: Optional[float] = None,
    expected_resolution: Optional[Tuple[int, int]] = None,
    expected_fps: Optional[int] = None,
    expected_codec: Optional[str] = None,
    has_audio: bool = True,
    duration_tolerance: float = 5.0,
) -> ValidationResult:
    """
    Convenience function for quick video validation.

    Args:
        video_path: Path to video file
        expected_duration: Expected duration in seconds (optional)
        expected_resolution: Expected (width, height) (optional)
        expected_fps: Expected FPS (optional)
        expected_codec: Expected codec name (optional)
        has_audio: Whether video should have audio (default: True)
        duration_tolerance: Duration tolerance in seconds (default: 5.0)

    Returns:
        ValidationResult with validation status
    """
```

### quick_validate()

Quick validation check - returns True if video appears valid.

```python
def quick_validate(video_path: Path) -> bool:
    """
    Quick validation check - returns True if video appears valid.

    Args:
        video_path: Path to video file

    Returns:
        True if video is readable and has basic properties
    """
```

### validate_ffmpeg_available()

Validate that FFmpeg and ffprobe are available.

```python
def validate_ffmpeg_available() -> ValidationResult:
    """
    Validate that FFmpeg and ffprobe are available.

    Returns:
        ValidationResult with tool availability status
    """
```

---

**Last Updated:** 2026-02-06

**Version:** 1.0

**Related Documentation:**
- User Guide: `docs/video-validation.md`
- Troubleshooting: `docs/internal-docs/validation/troubleshooting.md`
