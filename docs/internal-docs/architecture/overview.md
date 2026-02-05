# AutoVideo Architecture Overview

## System Components

The project consists of two main applications sharing a common core philosophy but differing in implementation details for testing purposes.

### 1. Main Video Renderer (`video_renderer/`)
The production-ready application.
- **Entry Point**: `main.py` (CLI/Wizard) or `tui.py` (Textual App).
- **Core Logic**: `ffmpeg.py`, `video.py`, `audio.py`.
- **UI**: Textual-based screens in `screens/`.

### 2. Ramtest Renderer (`video_renderer_ramtest/`)
A variant designed for testing logic changes or running in memory-constrained/specific environments.
- **Independence**: Originally a completely separate copy.
- **Integration**: Has been updated to optionally load the Core Logic from `video_renderer` to verify consistency.
- **UI**: Mirrors the main renderer's TUI but with added testing controls (e.g., "Use Main Renderer").

## Data Flow

### TUI State Management
The `VideoRendererApp` class holds the global application state:
- `queue`: A shared `BatchQueue` instance for managing render jobs across screens.
- `drive_folder_id`, `enable_upload`: Global settings for Drive integration.
- `render_mode`: Tracks if the user is in Single, Intro/Loop, or Batch mode.

### Rendering Pipeline
1. **Normalization**: Inputs are converted to a standard intermediate format (usually MP4, CFR).
2. **Concatenation**: Intro and Loop videos are concatenated.
3. **Audio Generation**: Music loops are created to match the video duration.
4. **Mixing**: Background audio is mixed with the music loop.
5. **Muxing**: Final video and audio are combined.

## Key Features

- **Smart Resolution**: In "Basic Mode", the pipeline analyzes source videos. If the intro and loop share a resolution, it is preserved to avoid unnecessary re-encoding loss.
- **Batch Processing**: A background thread (`BatchQueue`) manages jobs, allowing the UI to remain responsive.
- **Drive Integration**: Completed files can be uploaded to Google Drive automatically via `drive.py`.
