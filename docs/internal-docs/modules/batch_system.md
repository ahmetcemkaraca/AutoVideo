# Batch Rendering System

The batch system allows users to queue multiple render jobs, which are processed sequentially in a background thread.

## Core Components

### `RenderJob`
A dataclass representing a single unit of work.
- **Modes**:
  - `intro_loop`: Classic intro + loop concatenation.
  - `single`: Single video processing (e.g., format conversion, audio replacement).
- **State**: Tracks status (`PENDING`, `RUNNING`, `COMPLETE`, `ERROR`) and progress %.
- **Serialization**: Can be converted to/from dict for JSON storage (`batch_queue.json`).

### `BatchQueue`
A thread-safe manager for `RenderJob`s.
- **Persistence**: Automatically saves queue state to disk.
- **Callbacks**: Supports callbacks for progress updates, completion, and errors to update the UI.

### `SmartBatchDetector`
Scans a directory for file pairs matching the pattern `{name}_intro.mp4` and `{name}_loop.mp4` to automatically create batch jobs.

## Integration

The `BatchQueue` is initialized in the main `App` class and passed to the `BatchScreen`. This ensures that jobs added from `VideoSelectScreen` (via "Add to Batch") are visible and manageable in the `BatchScreen`.

## Single Video Mode
In `single` mode, the pipeline skips the concatenation step:
1. **Normalize/Encode**: The single video is processed to the target codec/resolution.
2. **Audio**: Music/Background logic is applied based on the video duration.
3. **Mux**: Final output is generated.
