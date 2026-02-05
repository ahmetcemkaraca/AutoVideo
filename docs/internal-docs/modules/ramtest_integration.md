# Ramtest Integration

The `video_renderer_ramtest` package serves as a testing ground. To ensure that tests are valid for the main application, it supports using the main application's logic core.

## Dynamic Import Logic

In `screens/render.py` and `screens/batch.py` of the ramtest package, the renderer classes are imported dynamically based on the `app.use_main_renderer` flag.

```python
if use_main:
    # Import from the main package (c:\Users\ahmet\Desktop\Dev\Video\video_renderer)
    from video_renderer.ffmpeg import FFmpegRunner
    from video_renderer.video import VideoEncoder
else:
    # Use local ramtest implementations
    from ..ffmpeg import FFmpegRunner
    from ..video import VideoEncoder
```

## Settings
A checkbox "Video Renderer Paketini Kullan" in the Ramtest Settings screen toggles this behavior. This allows developers to A/B test changes in the main logic without modifying the production environment directly or while testing UI changes in ramtest specific screens.
