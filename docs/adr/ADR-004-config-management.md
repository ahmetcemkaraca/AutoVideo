# ADR-004: Configuration Management Strategy

## Status
Accepted

## Context
The application requires multiple configuration sources:
- User preferences (codec, duration, etc.)
- System settings (hardware acceleration, paths)
- Component-specific configs (YouTube, Drive, etc.)
- Runtime state (batch queue, current job)

Challenges:
- Different formats (JSON, environment variables, CLI args)
- Validation requirements
- Default value management
- User experience for configuration
- Persistence across sessions

## Decision
Implement a hierarchical configuration system with:

1. **Multiple Sources**: CLI args > Config files > Defaults
2. **JSON Format**: Human-readable, easy to edit
3. **Validation**: Type checking and value validation
4. **Dataclasses**: Type-safe configuration objects
5. **Environment Variables**: For sensitive data (API keys)
6. **User Config**: `config.json` for user preferences
7. **Session Persistence**: `tmp/last_session.json` for resume capability

### Configuration Hierarchy

```
1. Command-line arguments (highest priority)
2. User config file (config.json)
3. Environment variables (for sensitive data)
4. Default values (lowest priority)
```

### Implementation Pattern

```python
@dataclass
class RenderConfig:
    """Complete configuration for a render session."""
    # Paths
    work_dir: Path = field(default_factory=Path.cwd)
    music_dir: Optional[Path] = None
    tmp_dir: Optional[Path] = None

    # Video settings
    width: int = DEFAULT_WIDTH
    height: int = DEFAULT_HEIGHT
    fps: int = 60
    codec: str = "av1"

    # Duration
    duration_seconds: int = 0

    def __post_init__(self):
        """Validate and set defaults."""
        if self.music_dir is None:
            self.music_dir = self.work_dir / "music"
        if self.tmp_dir is None:
            self.tmp_dir = self.work_dir / "tmp"
```

## Consequences

### Positive
- Flexible configuration from multiple sources
- Type-safe with dataclasses
- Easy to persist and restore
- Validation happens on object creation
- Sensitive data can use environment variables

### Negative
- Multiple files to manage
- Need to handle migration between config versions
- Validation logic can be complex

### Neutral
- JSON format limits some data types
- User needs to understand precedence

## Configuration Files

### config.json
```json
{
  "codec": "av1",
  "duration": "9:00:00",
  "width": 1920,
  "height": 1080,
  "fps": 60,
  "use_hw_accel": true,
  "parallel_encode": true
}
```

### client_secrets.json
```json
{
  "installed": {
    "client_id": "YOUR_CLIENT_ID",
    "client_secret": "YOUR_CLIENT_SECRET"
  }
}
```

## Best Practices

1. **Validation**: Validate on load, not use
2. **Defaults**: Provide sensible defaults
3. **Migration**: Handle old config versions
4. **Documentation**: Document all config options
5. **Security**: Never write secrets to config files

## Alternatives Considered

1. **YAML**: Use YAML instead of JSON
   - Rejected: Additional dependency, JSON sufficient

2. **Python Files**: Use .py files for config
   - Rejected: Security risk, not user-friendly

3. **Database**: Use SQLite for config storage
   - Rejected: Overkill for this use case

## Implementation

See: `video_renderer/config.py` for configuration dataclasses
See: `VideoAutomation/automation/config.py` for automation config

## Related Decisions
- ADR-002: Thread-safety strategy
- ADR-003: Logging architecture
