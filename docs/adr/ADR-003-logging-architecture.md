# ADR-003: Logging Architecture Strategy

## Status
Accepted

## Context
The application needs comprehensive logging for:
- Debugging rendering issues
- Tracking FFmpeg progress
- Monitoring batch operations
- Auditing user actions
- Troubleshooting integration issues

Challenges:
- Multiple components (renderer, automation, livestream)
- FFmpeg stderr parsing for progress
- User-facing vs. developer-facing logs
- Performance impact of logging
- Log file management

## Decision
Implement a hierarchical logging architecture with:

1. **Standard Library logging**: Python's built-in logging module
2. **Structured Logging**: Consistent format across components
3. **Log Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
4. **Multiple Handlers**: File, console, and optional remote
5. **Component-Specific Loggers**: Each module has its own logger
6. **FFmpeg Progress Parsing**: Custom parser for stderr

### Log Format

```python
# Structured log format
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
```

### Logger Hierarchy

```
AutoVideo (root)
├── video_renderer
│   ├── ffmpeg
│   ├── video
│   ├── audio
│   ├── batch
│   └── screens
├── VideoAutomation
│   ├── pipeline
│   ├── youtube
│   └── state
└── VideoLivestream
    ├── scheduler
    ├── mixer
    └── streamer
```

## Consequences

### Positive
- Consistent logging across all components
- Easy to filter by component or level
- Performance overhead minimal
- Easy to integrate with log aggregation tools
- FFmpeg progress captured accurately

### Negative
- Need to manage log file sizes
- Potential performance impact if DEBUG enabled
- FFmpeg parsing complexity

### Neutral
- Requires discipline to log appropriately
- Log rotation needed for long-running processes

## Implementation Guidelines

```python
# Component logging example
import logging

logger = logging.getLogger(__name__)

def render_video(config):
    logger.info(f"Starting render: {config.output_path}")
    try:
        # Rendering logic
        logger.debug(f"Using codec: {config.codec}")
    except Exception as e:
        logger.error(f"Render failed: {e}", exc_info=True)
        raise
```

## FFmpeg Progress Logging

Special handling for FFmpeg stderr:
- Parse frame/time/speed from stderr
- Update progress callbacks
- Log errors separately from progress
- Filter verbose FFmpeg output

## Alternatives Considered

1. **Print Statements**: Simple print() for everything
   - Rejected: No structure, can't control levels

2. **Third-Party Libraries**: Use structlog or loguru
   - Rejected: Additional dependency, stdlib sufficient

3. **No Logging**: Just use exceptions
   - Rejected: No visibility into issues

## Implementation

See: `video_renderer/tui.py` for console logging
See: `video_renderer/ffmpeg.py` for FFmpeg progress parsing

## Related Decisions
- ADR-001: video_renderer & ramtest integration
- ADR-002: Thread-safety strategy
