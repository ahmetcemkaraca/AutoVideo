# Ramtest Integration Strategy

**Date**: 2025-02-06
**Status**: ADR Draft
**Authors**: AutoVideo Production Team

---

## Status
**Proposed**

## Context

The AutoVideo project currently maintains two separate packages:
1. `video_renderer/` - Main production renderer
2. `video_renderer_ramtest/` - Testing variant with memory optimization features

This duplication creates several problems:
- Code maintenance burden (changes must be duplicated)
- Inconsistent behavior between packages
- Testing complexity
- User confusion

The ramtest package was originally created as a completely separate copy for testing logic changes in isolation. It has since gained the ability to dynamically import from the main package via a `use_main_renderer` flag.

## Decision

**Merge ramtest into the main video_renderer package using feature flags.**

### Key Points

1. **Single Codebase**: Maintain one `video_renderer/` package with all functionality
2. **Feature Flags**: Use configuration flags to enable test/optimization features
3. **Backward Compatibility**: Preserve ramtest functionality through deprecation period
4. **Clean Migration**: Provide clear migration path for existing users

## Implementation Plan

### Phase 1: Feature Flag Implementation (Week 1)

1. **Add test mode configuration** to `video_renderer/config.py`:
```python
@dataclass
class TestModeConfig:
    """Configuration for test/ramtest mode."""
    enabled: bool = False
    use_ramdisk: bool = False
    high_vram: bool = False
    chunk_long_videos: bool = False
    verbose_logging: bool = False
```

2. **Integrate RAM optimization features** from ramtest into main:
   - RAM disk detection and usage
   - High-VRAM optimization settings
   - Chunked processing for long videos

3. **Add TUI toggle** in Settings screen:
   - "Test Mode" checkbox
   - "Use RAM Disk" option
   - "High VRAM" option

### Phase 2: Update Ramtest Package (Week 2)

1. **Add deprecation notice** to ramtest:
```python
# video_renderer_ramtest/__init__.py
import warnings
warnings.warn(
    "video_renderer_ramtest is deprecated. "
    "Use video_renderer with TestModeConfig instead. "
    "See docs/migration/ramtest.md for details.",
    DeprecationWarning,
    stacklevel=2
)
```

2. **Make ramtest a thin wrapper** that imports from main:
```python
# Re-export everything from main package
from video_renderer import *
from video_renderer.config import TestModeConfig
```

### Phase 3: Documentation (Week 2)

1. **Create migration guide**: `docs/migration/ramtest.md`
2. **Update README.md** with test mode documentation
3. **Update CLAUDE.md** with unified architecture

### Phase 4: Testing (Week 3)

1. **Ensure all ramtest features work** in main package
2. **Add feature flag tests** to test suite
3. **Verify backward compatibility**

### Phase 5: Deprecation (After 3 months)

1. **Update ramtest to issue warnings**
2. **Document removal timeline**
3. **Plan final removal in next major version**

## Technical Details

### Feature Flags Implementation

```python
# video_renderer/config.py

@dataclass
class RenderConfig:
    # ... existing fields ...

    # Test mode configuration
    test_mode: TestModeConfig = field(default_factory=TestModeConfig)

@dataclass
class TestModeConfig:
    """Configuration for test/optimization mode."""
    enabled: bool = False
    use_ramdisk: bool = False
    high_vram: bool = False
    chunk_long_videos: bool = False

    def get_temp_dir(self, base_dir: Path) -> Path:
        """Get appropriate temp directory based on config."""
        if self.enabled and self.use_ramdisk:
            ramdisk = get_ramdisk_path()
            if ramdisk:
                ramdisk.mkdir(parents=True, exist_ok=True)
                return ramdisk
        return base_dir / "tmp"
```

### Migration Path for Users

**Before (ramtest)**:
```python
from video_renderer_ramtest import VideoRendererApp
app = VideoRendererApp()
app.run()
```

**After (main with test mode)**:
```python
from video_renderer import VideoRendererApp, TestModeConfig

# Enable test mode via config
config = TestModeConfig(
    enabled=True,
    use_ramdisk=True,
    high_vram=True
)

app = VideoRendererApp(test_mode=config)
app.run()
```

## Consequences

### Positive

1. **Reduced Maintenance**: Single codebase to maintain
2. **Consistent Behavior**: All features in one package
3. **Better Testing**: Easier to test feature interactions
4. **Clearer Architecture**: No duplicate packages
5. **Easier Onboarding**: New users only need to know one package

### Negative

1. **Migration Effort**: Existing ramtest users need to update
2. **Complexity**: Main package gains more configuration options
3. **Backward Compatibility**: Need to maintain shim during deprecation

### Neutral

1. **Package Size**: Slightly larger due to additional features
2. **Configuration**: More options to configure (but with sensible defaults)

## Alternatives Considered

### Alternative 1: Keep Separate Packages
**Rejected**: Continued maintenance burden, user confusion

### Alternative 2: Complete Removal
**Rejected**: Would break existing users, lose useful features

### Alternative 3: Plugin System
**Rejected**: Over-engineering for this use case, adds complexity

## References

- Original ramtest implementation: `video_renderer_ramtest/`
- Main package: `video_renderer/`
- RAM optimization code: `video_renderer/config.py` lines 348-513

---

**End of ADR-005**
