# TUI Screens Module

The screens module (`video_renderer/screens/`) contains all Textual TUI screens for the video renderer application.

## Overview

The TUI (Terminal User Interface) provides an interactive, keyboard-driven interface for video rendering. Built with Textual framework, it offers:

- Mode selection (Single, Intro/Loop, Batch)
- Video file selection with preview
- Audio track selection with validation
- Settings configuration
- Real-time render progress
- Batch queue management
- Smart batch detection

## Screen Reference

### ModeSelectScreen

**File:** `mode_select.py`

First screen shown when TUI starts. Allows user to select render mode.

**Modes:**
- **Single**: Process a single video file
- **Intro/Loop**: Classic intro + loop concatenation
- **Batch**: Queue multiple render jobs

**Key Bindings:**
- `Enter`: Select mode
- `q`: Quit application

### HomeScreen

**File:** `home.py`

Main navigation hub after mode selection.

**Features:**
- Quick access to all functions
- Current settings display
- Recent jobs list

### VideoSelectScreen

**File:** `video_select.py`

Video file selection with preview and multi-select support.

**Features:**
- Directory browsing
- File preview (codec, resolution, duration)
- Multi-select with Space key
- Filter by extension
- Sort by name/date/size

**Key Bindings:**
- `Enter`: Select/Deselect file
- `Space`: Toggle selection (multi-select)
- `f`: Toggle filter
- `s`: Change sort order

### AudioSelectScreen

**File:** `audio_select.py`

Audio track selection with validation and background detection.

**Features:**
- Track validation status
- Background auto-detection
- Gain preview from filename
- Track duration display
- Total duration calculation

**Key Bindings:**
- `Enter`: Select/Deselect track
- `Space`: Toggle selection
- `v`: Validate all tracks
- `r`: Refresh track list

### SettingsScreen

**File:** `settings.py`

Configuration settings for rendering.

**Settings:**
- Codec selection (H.264, H.265, AV1)
- Resolution (1080p, 1440p, 4K)
- Duration (preset or custom)
- Hardware acceleration toggle
- Google Drive upload toggle
- Output directory

**Key Bindings:**
- `Tab`: Next setting
- `Shift+Tab`: Previous setting
- `Enter`: Edit setting
- `s`: Save settings

### RenderScreen

**File:** `render.py`

Real-time rendering progress display.

**Features:**
- Current step indicator
- Progress bars for each phase
- FPS and speed display
- Estimated time remaining
- Memory usage (in ramtest mode)
- Error display and retry

**Progress Phases:**
1. Validating input files
2. Normalizing intro video
3. Normalizing loop video
4. Concatenating videos
5. Processing audio
6. Muxing final output
7. Uploading (if enabled)

**Key Bindings:**
- `p`: Pause render
- `c`: Cancel render
- `l`: Show log

### CompleteScreen

**File:** `complete.py`

Render completion summary.

**Features:**
- Output file info (size, duration, codec)
- Render statistics (time, average FPS)
- Open output folder
- Upload status
- Start new render option

**Key Bindings:**
- `n`: New render
- `o`: Open output folder
- `u`: Upload to Drive
- `q`: Quit

### BatchScreen

**File:** `batch.py`

Batch queue management interface.

**Features:**
- Job list with status
- Add/remove jobs
- Reorder jobs
- Job configuration preview
- Start/pause/stop queue

**Job Status:**
- `pending`: Waiting to start
- `running`: Currently rendering
- `completed`: Finished successfully
- `failed`: Error occurred
- `cancelled`: User cancelled

**Key Bindings:**
- `a`: Add new job
- `d`: Delete selected job
- `Enter`: Edit job
- `Space`: Start/stop queue
- `r`: Retry failed jobs

### SmartBatchScreen

**File:** `smart_batch.py`

Auto-detection of intro/loop video pairs.

**Features:**
- Scan directory for pairs
- Pattern matching (`*_intro.mp4` + `*_loop.mp4`)
- Preview detected pairs
- Batch add to queue

**Detection Patterns:**
- `{name}_intro.mp4` / `{name}_loop.mp4`
- `{name}-intro.mp4` / `{name}-loop.mp4`
- `{name}intro.mp4` / `{name}loop.mp4`

**Key Bindings:**
- `s`: Scan directory
- `a`: Add all to queue
- `Enter`: Preview pair
- `f`: Change scan folder

### ValidationScreen

**File:** `validation_screen.py`

File validation results display.

**Features:**
- Validation status for each file
- Error details
- Suggestions for fixing issues
- Batch validation

### ValidationResultsScreen

**File:** `validation.py`

Alternative validation display with different layout.

## Styling

All screens use a shared stylesheet (`styles.tcss`):

```css
/* Main colors */
$primary: #3d5a80;
$secondary: #98c1d9;
$accent: #ee6c4d;
$background: #293241;
$text: #e0fbfc;

/* Components */
.button {
    background: $primary;
    color: $text;
    padding: 1 2;
}

.selected {
    background: $accent;
}

.progress-bar {
    height: 1;
    background: $secondary;
}
```

## Application State

Global state is managed in `VideoRendererApp` (app.py):

```python
class VideoRendererApp(App):
    # Shared state
    queue: BatchQueue
    drive_folder_id: Optional[str]
    enable_upload: bool
    render_mode: str  # "single", "intro_loop", "batch"

    # Current job
    intro_path: Optional[Path]
    loop_path: Optional[Path]
    audio_tracks: List[Path]
    background_tracks: List[Tuple[Path, float]]
```

## Navigation Flow

```
ModeSelectScreen
       │
       ▼
   HomeScreen
       │
       ├─► VideoSelectScreen
       │        │
       │        ▼
       │   AudioSelectScreen
       │        │
       │        ▼
       │   SettingsScreen
       │        │
       │        ▼
       │   RenderScreen
       │        │
       │        ▼
       │   CompleteScreen
       │
       └─► BatchScreen
                │
                ├─► VideoSelectScreen
                └─► SmartBatchScreen
```

## Key Bindings (Global)

| Key | Action |
|-----|--------|
| `q` | Quit application |
| `Esc` | Go back / Cancel |
| `Tab` | Next focus |
| `Shift+Tab` | Previous focus |
| `?` | Show help |
| `Ctrl+C` | Force quit |

## Creating Custom Screens

```python
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Static

class CustomScreen(Screen):
    """Custom screen example."""

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Custom content")
        yield Footer()

    def on_mount(self) -> None:
        """Called when screen is mounted."""
        pass

    def key_enter(self) -> None:
        """Handle Enter key."""
        pass
```

## See Also

- [Textual Documentation](https://textual.textual.io/)
- [Batch System](batch_system.md) - Batch processing
- [VideoEncoder](video_encoder.md) - Video encoding
