# AutoVideo System Design

## Overview

AutoVideo is a Python-based video rendering and automation system designed to create long-duration videos (8-10 hours) by combining intro + loop videos with processed audio tracks.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Interface Layer                    │
├─────────────────┬─────────────────┬─────────────────────────────┤
│   CLI Wizard    │  TUI (Textual)  │    Automation Pipeline      │
│   (main.py)     │   (app.py)      │   (run_automation.py)       │
└────────┬────────┴────────┬────────┴───────────┬─────────────────┘
         │                 │                    │
         ▼                 ▼                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Application Logic Layer                    │
├─────────────────┬─────────────────┬─────────────────────────────┤
│  Batch System   │  Render Engine  │    Integration Layer        │
│  (batch.py)     │  (video.py)     │  (drive.py, youtube.py)     │
└────────┬────────┴────────┬────────┴───────────┬─────────────────┘
         │                 │                    │
         ▼                 ▼                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Core Services Layer                        │
├─────────────────┬─────────────────┬─────────────────────────────┤
│   FFmpeg        │   Audio         │    Configuration            │
│   (ffmpeg.py)   │   (audio.py)    │    (config.py)              │
└─────────────────┴─────────────────┴─────────────────────────────┘
```

## Core Components

### 1. Video Renderer (`video_renderer/`)

The main rendering engine responsible for video processing.

**Key Classes**:
- `VideoEncoder`: Handles video encoding, normalization, concatenation
- `AudioProcessor`: Processes audio tracks, looping, mixing
- `FFmpegRunner`: Executes FFmpeg commands with progress tracking
- `BatchQueue`: Manages render jobs with thread-safe operations
- `SmartBatchDetector`: Auto-detects intro/loop pairs

**Workflow**:
```
1. Input Selection → User selects intro/loop videos
2. Audio Selection → User selects music and background tracks
3. Configuration   → User configures codec, duration, resolution
4. Validation      → System validates inputs and configuration
5. Rendering       → Parallel video and audio processing
6. Muxing          → Combine video and audio
7. Output          → Final video file created
8. Upload          → Optional cloud upload (Drive/YouTube)
```

### 2. VideoAutomation (`VideoAutomation/`)

Automated pipeline for continuous video generation with YouTube upload.

**Key Classes**:
- `AutomationPipeline`: Orchestrates end-to-end automation
- `YouTubeUploader`: Handles YouTube API interactions
- `AutomationConfig`: Manages automation configuration
- `AutomationState`: Persists state across sessions

**Workflow**:
```
1. Load Config   → Read settings and metadata templates
2. Select Media  → Randomly select from available media
3. Render Video  → Use core rendering engine
4. Upload        → Upload to YouTube with metadata
5. Update State  → Track generated videos and statistics
6. Loop          → Repeat in continuous mode
```

### 3. VideoLivestream (`VideoLivestream/`)

Automated playlist generation for YouTube livestreams.

**Key Classes**:
- `StreamScheduler`: Manages stream scheduling
- `ContentMixer`: Mixes content sets
- `StreamManager`: Handles stream lifecycle

**Workflow**:
```
1. Initialize     → Set up content directories
2. Generate       → Create playlists with variations
3. Schedule       → Schedule streams
4. Execute        → Run scheduled streams
```

## Data Flow

### Render Pipeline

```
┌──────────────┐
│ Intro Video  │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Normalize   │ → Convert to standard format
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Loop Video   │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Normalize   │ → Convert to standard format
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Concat      │ → Combine to target duration
└──────┬───────┘
       │
       ├──┐
       │  │
       ▼  ▼
┌──────────────┐    ┌──────────────┐
│ Audio Track  │    │  Background  │
└──────┬───────┘    └──────┬───────┘
       │                   │
       ▼                   ▼
┌──────────────┐    ┌──────────────┐
│  Loop Audio  │    │  Mix Audio   │
└──────┬───────┘    └──────┬───────┘
       │                   │
       └─────────┬─────────┘
                 ▼
         ┌──────────────┐
         │    Mux       │ → Combine video + audio
         └──────┬───────┘
                │
                ▼
         ┌──────────────┐
         │  Output      │ → Final video file
         └──────────────┘
```

### Batch Processing

```
┌──────────────┐
│ User Config  │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Create Job  │ → RenderJob object
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Queue Job    │ → Add to BatchQueue
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Worker      │ → Background thread
└──────┬───────┘
       │
       ├───┐
       │   │
       ▼   ▼
┌─────────┐ ┌──────────┐
│ Render  │ │ Upload   │
└────┬────┘ └────┬─────┘
     │           │
     └─────┬─────┘
           ▼
    ┌──────────────┐
    │ Notify User  │ → Callback/Event
    └──────────────┘
```

## Technology Stack

### Core Technologies
- **Python 3.10+**: Primary language
- **FFmpeg**: Video/audio processing engine
- **Textual**: TUI framework
- **Rich**: Terminal output formatting

### External Services
- **Google Drive API**: Cloud storage integration
- **YouTube Data API v3**: Video upload and management

### Hardware Acceleration
- **NVIDIA NVENC**: H.264, H.265, AV1 encoding
- **Intel QSV**: H.264, H.265 encoding
- **VAAPI**: H.264, H.265 encoding (Linux)

## Design Patterns

### 1. Strategy Pattern
Different codec configurations (AV1, H.264, H.265) use a common interface.

### 2. Observer Pattern
Batch queue uses callbacks to notify UI of progress updates.

### 3. Factory Pattern
Encoder selection based on available hardware.

### 4. Builder Pattern
Render configuration built step-by-step in CLI wizard.

### 5. Singleton Pattern
TUI app instance manages global state.

## Concurrency Model

### Threading
- **Main Thread**: UI event handling
- **Worker Thread**: Video rendering
- **Upload Thread**: Cloud uploads
- **Progress Thread**: FFmpeg progress parsing

### Thread Safety
- Threading locks for shared state
- Queue for producer-consumer patterns
- Callbacks for cross-thread communication

## Error Handling Strategy

### Exception Hierarchy
```
AutoVideoError
├── RenderError
│   ├── VideoEncodingError
│   ├── AudioProcessingError
│   └── MuxingError
├── ConfigError
│   ├── ValidationError
│   └── MissingConfigError
├── UploadError
│   ├── DriveUploadError
│   └── YouTubeUploadError
└── FFmpegError
```

### Error Recovery
- Validate inputs before processing
- Check FFmpeg availability
- Handle hardware encoder failures
- Retry failed uploads
- Preserve state for resume capability

## Performance Considerations

### Optimization Strategies
1. **Hardware Acceleration**: Use GPU encoders when available
2. **Parallel Processing**: Video and audio processed concurrently
3. **Smart Resolution**: Avoid re-encoding when possible
4. **Efficient Concat**: Use concat demuxer for long videos
5. **Progressive Encoding**: Stream-based processing for large files

### Memory Management
- Stream-based FFmpeg processing
- Temporary file cleanup
- Audio chunking for large tracks
- Memory-efficient concat list generation

## Security Considerations

### Credential Management
- OAuth 2.0 for Google services
- Token storage in user home directory
- No credentials in config files
- Token refresh on expiry

### File Operations
- Validate file paths
- Sanitize filenames
- Check file permissions
- Limit file sizes

## Extensibility Points

### Adding New Codecs
```python
# In config.py
CODEC_NEW = CodecConfig(
    name="New Codec",
    encoder="new_encoder",
    preset="medium",
    crf=20,
)
```

### Adding New Upload Targets
```python
# Implement interface
class NewUploader:
    def upload(self, file_path: Path) -> str:
        pass
```

### Adding New Audio Processors
```python
# Extend AudioProcessor
class CustomProcessor(AudioProcessor):
    def process(self, tracks: List[Path]) -> Path:
        pass
```

## Monitoring and Observability

### Logging
- Component-specific loggers
- Structured log format
- Multiple log levels
- FFmpeg progress tracking

### Metrics
- Render duration
- Encoding speed
- File sizes
- Upload success rates
- Error counts

## Deployment Considerations

### Platform Support
- **Windows**: Primary development platform
- **Linux**: VPS deployment support
- **macOS**: Community support

### Dependencies
- System: FFmpeg
- Python: See requirements.txt
- Hardware: GPU for acceleration (optional)

### Configuration
- User config: `config.json`
- Session state: `tmp/last_session.json`
- Batch queue: `tmp/batch_queue.json`

## Future Architecture Evolution

### Planned Improvements
1. **Microservices**: Split into separate services
2. **Message Queue**: RabbitMQ/Redis for job distribution
3. **REST API**: Web UI backend
4. **Database**: PostgreSQL for state management
5. **Containerization**: Docker deployment
6. **Distributed Rendering**: Multiple worker nodes

---

**Document Version**: 1.0
**Last Updated**: 2024-01-XX
**Author**: AutoVideo Development Team
