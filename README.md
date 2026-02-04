# AutoVideo - Video Renderer & Automation System

Advanced video rendering and automation system with Batch processing, TUI (Terminal User Interface), and Google Drive integration.

## Features

- **Batch Rendering**: Queue multiple render jobs with distinct configurations.
- **Smart Batch**: Automatically detect `*_intro.mp4` and `*_loop.mp4` pairs.
- **Background Upload**: Automatically upload rendered videos to Google Drive while processing the next job.
- **Duration Options**: Fixed presets, Custom HH:MM:SS, or Random (8-10 hours).
- **Format Support**: AV1, H.264, H.265/HEVC encoding with hardware acceleration support.
- **Live TUI**: Rich Terminal User Interface built with Textual.

## Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/USERNAME/AutoVideo.git
    cd AutoVideo
    ```

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Google Drive Setup** (Optional):
    -   Place your `client_secrets.json` file in the project root.
    -   The first time you upload, a browser window will open to authenticate.

## Usage

### Interactive TUI Mode
Run the modern TUI interface:
```bash
python -m video_renderer --tui
```
-   **Batch**: Manage queue, add jobs, view progress.
-   **Settings**: Configure rendering options, enable Drive upload.
-   **Smart Batch**: Auto-detect video pairs in the working directory.

### CLI Mode
Basic interactive wizard:
```bash
python -m video_renderer
```

## Structure

-   `video_renderer/`: Main package.
    -   `screens/`: TUI screens (Batch, Settings, etc.).
    -   `drive.py`: Google Drive integration.
    -   `batch.py`: Job queue management.
    -   `ffmpeg.py` & `video.py`: Core rendering logic.
-   `scripts/`: Helper scripts.

## Requirements

-   Python 3.8+
-   FFmpeg installed and in system PATH.
