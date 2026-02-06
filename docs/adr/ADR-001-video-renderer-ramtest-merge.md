# ADR-001: video_renderer & ramtest Integration Strategy

## Status
Accepted

## Context
The project has two similar implementations:
1. `video_renderer/` - Production-ready main renderer
2. `video_renderer_ramtest/` - Testing variant for memory-constrained environments

These implementations were initially separate copies, leading to:
- Code duplication
- Inconsistency between implementations
- Maintenance overhead
- Difficulty verifying which version has the latest features

## Decision
Implement a hybrid approach where `video_renderer_ramtest/` can optionally load core logic from the main `video_renderer/` while maintaining its independence for testing purposes.

### Implementation Details

1. **Maintain Separate Structure**: Both packages remain independent
2. **Optional Core Loading**: Ramtest can load main renderer's core modules when needed
3. **Toggle Switch**: TUI includes "Use Main Renderer" toggle for runtime switching
4. **Shared Interfaces**: Common interfaces ensure compatibility

```python
# In video_renderer_ramtest/app.py
def load_main_renderer():
    """Optionally load core logic from main renderer."""
    try:
        from video_renderer.video import VideoEncoder
        from video_renderer.audio import AudioProcessor
        return VideoEncoder, AudioProcessor
    except ImportError:
        from video_renderer_ramtest.video import VideoEncoder
        from video_renderer_ramtest.audio import AudioProcessor
        return VideoEncoder, AudioProcessor
```

## Consequences

### Positive
- Reduces code duplication for core logic
- Allows testing changes in isolated environment
- Easy to verify consistency between implementations
- Maintains independence for specialized testing
- Runtime flexibility to switch implementations

### Negative
- Slight complexity in import logic
- Need to maintain interface compatibility
- Testing both code paths required

### Neutral
- Both packages continue to exist
- Package size slightly increased due to optional imports

## Alternatives Considered

1. **Complete Merge**: Remove ramtest, add testing flags to main renderer
   - Rejected: Testing needs isolation from production code

2. **Complete Separation**: Keep as totally independent packages
   - Rejected: Too much duplication, maintenance burden

3. **Symlink Approach**: Use symlinks for shared files
   - Rejected: Cross-platform compatibility issues

## Implementation

See: `video_renderer_ramtest/app.py` for toggle implementation

## Related Decisions
- ADR-002: Thread-safety strategy
- ADR-003: Logging architecture
