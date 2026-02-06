# AutoVideo v1.0.0 - Architecture Diagrams
**Version**: 1.0.0
**Last Updated**: 2025-02-06

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Component Diagrams](#component-diagrams)
3. [Data Flow Diagrams](#data-flow-diagrams)
4. [Sequence Diagrams](#sequence-diagrams)
5. [Deployment Architecture](#deployment-architecture)
6. [Class Hierarchy](#class-hierarchy)

---

## System Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         AutoVideo System                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │   TUI/CLI   │  │ VideoAutomation│ │ VideoLivestream│          │
│  │   Interface │  │   Pipeline    │  │   Pipeline    │          │
│  └──────┬──────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                │                   │                   │
│         └────────────────┼───────────────────┘                   │
│                          │                                       │
│                   ┌──────▼──────┐                                │
│                   │ Core Renderer│                               │
│                   │   Module     │                               │
│                   └──────┬──────┘                                │
│                          │                                       │
│  ┌───────────────────────┼───────────────────────┐              │
│  │                       │                       │              │
│  ▼                       ▼                       ▼              │
│ ┌────────┐         ┌─────────┐           ┌──────────┐           │
│ │ Video  │         │  Audio  │           │  Batch   │           │
│ │Encoder │         │Processor│           │  Queue   │           │
│ └───┬────┘         └────┬────┘           └────┬─────┘           │
│     │                   │                    │                   │
│     └───────────────────┴────────────────────┘                   │
│                          │                                       │
│                   ┌──────▼──────┐                                │
│                   │  FFmpeg     │                                │
│                   │  Executor   │                                │
│                   └──────┬──────┘                                │
│                          │                                       │
└──────────────────────────┼───────────────────────────────────────┘
                           │
                           ▼
                   ┌──────────────┐
                   │  File System │
                   │  + Hardware  │
                   └──────────────┘
```

---

## Component Diagrams

### Core Renderer Components

```
┌─────────────────────────────────────────────────────────────────┐
│                     video_renderer Package                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                     Entry Points                          │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │  main.py          - CLI entry point                      │  │
│  │  app.py           - TUI application                      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                   Core Components                         │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │  video.py         - VideoEncoder class                    │  │
│  │  audio.py         - AudioProcessor class                  │  │
│  │  ffmpeg.py        - FFmpegRunner class                    │  │
│  │  batch.py         - BatchQueue, RenderJob classes         │  │
│  │  config.py        - Configuration management              │  │
│  │  drive.py         - Google Drive integration              │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                  Security Modules                         │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │  security.py      - Input validation                      │  │
│  │  secrets.py       - Credential management                 │  │
│  │  audit.py         - Security logging                      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    TUI Screens                            │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │  screens/home.py   - Main menu                            │  │
│  │  screens/batch.py  - Batch management                     │  │
│  │  screens/render.py- Rendering screen                      │  │
│  │  screens/settings.py- Settings management                 │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Configuration System

```
┌────────────────────────────────────────────────────────────────┐
│                    Configuration Hierarchy                      │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Priority (Highest → Lowest):                                   │
│                                                                  │
│  1. CLI Flags                                                   │
│     ┌──────────────────────────────────┐                       │
│     │ --codec, --preset, --duration,   │                       │
│     │ --hw-accel, --ramtest, --output  │                       │
│     └──────────────┬───────────────────┘                       │
│                    │                                            │
│  2. Environment Variables                                       │
│     ┌──────────────────────────────────┐                       │
│     │ AUTOVIDEO_CODEC, CRF, HW_ACCEL   │                       │
│     │ YOUTUBE_ENABLED, DRIVE_FOLDER_ID │                       │
│     └──────────────┬───────────────────┘                       │
│                    │                                            │
│  3. Config File (config.json)                                   │
│     ┌──────────────────────────────────┐                       │
│     │ {                                 │                       │
│     │   "encoder": {...},               │                       │
│     │   "audio": {...},                 │                       │
│     │   "youtube": {...}                │                       │
│     │ }                                 │                       │
│     └──────────────┬───────────────────┘                       │
│                    │                                            │
│  4. Default Values (in code)                                    │
│     ┌──────────────────────────────────┐                       │
│     │ codec="libx264", preset="medium",│                       │
│     │ crf=23, output_dir="output"      │                       │
│     └──────────────────────────────────┘                       │
│                                                                  │
│  Result: RenderConfig object                                    │
│                                                                  │
└────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Diagrams

### Render Pipeline Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Video Render Pipeline                        │
└─────────────────────────────────────────────────────────────────┘

Input Videos                    Temp Files                    Output
┌─────────┐                   ┌─────────┐                  ┌─────────┐
│ intro   │                   │normalized│                  │final    │
│ loop    │ ──────────────▶   │ videos   │ ──────────────▶  │ video   │
└─────────┘                   └─────────┘                  └─────────┘
     │                              │                            │
     │                              │                            │
     ▼                              ▼                            ▼
┌─────────┐                   ┌─────────┐                  ┌─────────┐
│ FFmpeg  │                   │concat   │                  │ FFmpeg  │
│probe    │                   │ list    │                  │ mux     │
└─────────┘                   └─────────┘                  └─────────┘
     │                              │                            │
     │                              │                            │
     ▼                              ▼                            ▼
┌─────────┐                   ┌─────────┐                  ┌─────────┐
│check    │                   │calculate│                  │upload   │
│compat   │                   │loops    │                  │to Drive │
└─────────┘                   └─────────┘                  └─────────┘

Audio Pipeline (Parallel):
┌─────────┐                   ┌─────────┐                  ┌─────────┐
│ music   │                   │looped   │                  │mixed    │
│ tracks  │ ──────────────▶   │tracks   │ ──────────────▶  │ audio   │
└─────────┘                   └─────────┘                  └─────────┘
     │                              │                            │
     ▼                              ▼                            ▼
┌─────────┐                   ┌─────────┐                  ┌─────────┐
│validate │                   │apply    │                  │normalize│
│tracks   │                   │gain     │                  │levels   │
└─────────┘                   └─────────┘                  └─────────┘
```

### Batch Processing Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                      Batch Queue System                         │
└─────────────────────────────────────────────────────────────────┘

User Input                     Queue                      Execution
┌─────────┐                   ┌─────────┐                  ┌─────────┐
│ select  │                   │pending  │                  │active   │
│ videos  │ ──────────────▶   │ jobs    │ ──────────────▶  │ job     │
└─────────┘                   └─────────┘                  └─────────┘
     │                              │                            │
     ▼                              ▼                            ▼
┌─────────┐                   ┌─────────┐                  ┌─────────┐
│ create  │                   │load     │                  │process  │
│ RenderJob│                   │ queue   │                  │ job     │
└─────────┘                   └─────────┘                  └─────────┘
     │                              │                            │
     ▼                              ▼                            ▼
┌─────────┐                   ┌─────────┐                  ┌─────────┐
│ add to  │                   │persist  │                  │callback │
│ queue   │                   │ to disk │                  │notify   │
└─────────┘                   └─────────┘                  └─────────┘

Thread Safety:
┌─────────────────────────────────────────────────────────┐
│  RLock for queue operations                             │
│  Separate lock for callbacks                            │
│  Atomic file writes (temp + rename)                     │
│  Deep copy returns                                      │
└─────────────────────────────────────────────────────────┘
```

---

## Sequence Diagrams

### Single Render Sequence

```
User          CLI/TUI        VideoEncoder    FFmpegRunner    File System
 │              │                │                │                │
 │──render()────▶│                │                │                │
 │              │                │                │                │
 │              │──encode()──────▶│                │                │
 │              │                │                │                │
 │              │                │──probe()───────▶│                │
 │              │                │                │                │
 │              │                │                │──read metadata▶│
 │              │                │                │                │
 │              │                │                │◀─info──────────│
 │              │                │                │                │
 │              │                │──normalize()───▶│                │
 │              │                │                │                │
 │              │                │                │──encode───────▶│
 │              │                │                │                │
 │              │                │                │◀─progress──────│
 │              │                │                │                │
 │              │                │◀─result────────│                │
 │              │                │                │                │
 │              │──mix_audio()───▶│                │                │
 │              │                │                │                │
 │              │──concat()──────▶│                │                │
 │              │                │                │                │
 │              │──mux()─────────▶│                │                │
 │              │                │                │                │
 │              │◀─complete──────│                │                │
 │◀─result──────│                │                │                │
```

### Batch Render Sequence

```
User          BatchQueue      WorkerThread    VideoEncoder    File System
 │                │                │                │                │
 │──add jobs─────▶│                │                │                │
 │                │                │                │                │
 │                │──save()─────────────────────────────────────────▶│
 │                │                │                │                │
 │──start queue──▶│                │                │                │
 │                │                │                │                │
 │                │──next job─────▶│                │                │
 │                │                │                │                │
 │                │                │──encode()──────▶│                │
 │                │                │                │                │
 │                │                │                │──process──────▶│
 │                │                │                │                │
 │                │◀─progress──────│                │                │
 │◀─update────────│                │                │                │
 │                │                │                │                │
 │                │                │◀─complete──────│                │
 │                │──update status▶│                │                │
 │                │                │                │                │
 │                │──callback─────▶│                │                │
 │◀─notification──│                │                │                │
 │                │                │                │                │
 │                │──next job─────▶│ (repeat for each job)
```

---

## Deployment Architecture

### Development Environment

```
┌─────────────────────────────────────────────────────────────────┐
│                   Development Setup                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Developer Machine                                               │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  IDE/Editor (VS Code, PyCharm)                          │   │
│  │    ├── Git                                              │   │
│  │    ├── Python 3.10+                                     │   │
│  │    └── Virtual Environment                             │   │
│  └──────────────────┬──────────────────────────────────────┘   │
│                     │                                            │
│                     ▼                                            │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Project Directory                                      │   │
│  │    ├── video_renderer/                                  │   │
│  │    ├── tests/                                           │   │
│  │    ├── docs/                                            │   │
│  │    └── VideoAutomation/                                 │   │
│  └─────────────────────────────────────────────────────────┘   │
│                     │                                            │
│                     ▼                                            │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Local Development Tools                                │   │
│  │    ├── pytest (testing)                                 │   │
│  │    ├── FFmpeg (local install)                           │   │
│  │    └── Sample videos                                    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Production Deployment

```
┌─────────────────────────────────────────────────────────────────┐
│                  Production Deployment                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────┐        ┌─────────────────┐                │
│  │   VPS/Server    │        │   Storage       │                │
│  │  (Linux)        │        │   (NFS/S3)      │                │
│  ├─────────────────┤        ├─────────────────┤                │
│  │ Docker/Podman   │◀──────▶│ Video Input     │                │
│  │  ┌───────────┐  │        │ Video Output    │                │
│  │  │AutoVideo  │  │        │ Music Files     │                │
│  │  │Container  │  │        │ Archive         │                │
│  │  └───────────┘  │        └─────────────────┘                │
│  │    │            │                                          │
│  │    ▼            │        ┌─────────────────┐                │
│  │ ┌─────────────┐ │        │ External APIs   │                │
│  │ │FFmpeg       │ │        ├─────────────────┤                │
│  │ │(hw accel)   │ │        │ Google Drive    │                │
│  │ └─────────────┘ │        │ YouTube         │                │
│  └─────────────────┘        └─────────────────┘                │
│           │                                                     │
│           │ Schedule/Trigger                                    │
│           ▼                                                     │
│  ┌─────────────────┐                                           │
│  │ Cron/Systemd    │                                           │
│  │ Timer          │                                           │
│  └─────────────────┘                                           │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Class Hierarchy

### Core Classes

```
RenderConfig (dataclass)
│
├── codec: str
├── preset: str
├── crf: int
├── duration: Duration
├── output_path: Path
└── ramtest_config: RamTestConfig

RamTestConfig (dataclass)
│
├── enabled: bool
├── use_ramdisk: bool
├── high_vram: bool
└── chunk_long_videos: bool

RenderJob (dataclass)
│
├── id: str
├── config: RenderConfig
├── status: JobStatus
├── progress: float
├── created_at: datetime
└── completed_at: Optional[datetime]

JobStatus (Enum)
│
├── PENDING
├── IN_PROGRESS
├── COMPLETED
├── FAILED
└── CANCELLED
```

### Component Classes

```
VideoEncoder
│
├── __init__(config: RenderConfig)
├── encode_video(input_path: Path) -> Path
├── normalize_video(input_path: Path) -> Path
├── concat_videos(videos: List[Path], duration: int) -> Path
└── check_compatibility(video_path: Path) -> bool

AudioProcessor
│
├── __init__(config: AudioConfig)
├── loop_audio(audio_path: Path, duration: int) -> Path
├── mix_audio(tracks: List[Path], background: Path) -> Path
├── validate_audio(audio_path: Path) -> bool
└── detect_gain(filename: str) -> float

FFmpegRunner
│
├── __init__()
├── run_command(args: List[str]) -> CompletedProcess
├── probe_video(video_path: Path) -> VideoInfo
├── parse_progress(line: str) -> Optional[Progress]
└── get_available_encoders() -> List[str]

BatchQueue
│
├── __init__(persistence_path: Path)
├── add_job(job: RenderJob) -> str
├── get_job(job_id: str) -> Optional[RenderJob]
├── update_job(job_id: str, **kwargs) -> bool
├── remove_job(job_id: str) -> bool
├── get_next_job() -> Optional[RenderJob]
├── save() -> None
└── load() -> None
```

### Exception Hierarchy

```
VideoRendererError (Exception)
│
├── FFmpegError
│   ├── FFmpegNotFoundError
│   ├── EncodingError
│   └── CodecNotFoundError
│
├── AudioError
│   ├── AudioValidationError
│   ├── AudioProcessingError
│   └── TrackNotFoundError
│
├── ValidationError
│   ├── PathValidationError
│   ├── ConfigValidationError
│   └── FileValidationError
│
├── SecurityError
│   ├── PathTraversalError
│   ├── CommandInjectionError
│   └── CredentialError
│
└── UploadError
    ├── GoogleDriveError
    └── YouTubeUploadError
```

---

## Module Dependencies

```
                    ┌──────────────┐
                    │   main.py    │
                    │   app.py     │
                    └──────┬───────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  video.py    │  │  audio.py    │  │  batch.py    │
│  (VideoEncoder)│ │(AudioProcessor)│ │(BatchQueue)  │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       └─────────────────┼─────────────────┘
                         │
                         ▼
                 ┌──────────────┐
                 │  ffmpeg.py   │
                 │(FFmpegRunner)│
                 └──────┬───────┘
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  config.py   │ │ security.py  │ │  audit.py    │
│(Config)      │ │(Validation)  │ │(Logging)     │
└──────────────┘ └──────────────┘ └──────────────┘
```

---

**Last Updated**: 2025-02-06
**Version**: 1.0.0
