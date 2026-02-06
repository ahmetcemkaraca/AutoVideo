# ADR-002: Thread-Safety Strategy for Batch Processing

## Status
Accepted

## Context
The batch rendering system requires concurrent operations:
- Background video encoding
- Audio processing
- UI updates
- File uploads
- State persistence

Without proper thread safety, this leads to:
- Race conditions on shared state
- Inconsistent queue state
- Lost progress updates
- UI flickering/freezing

## Decision
Implement a comprehensive thread-safety strategy using:

1. **Threading Locks**: Protect all shared state modifications
2. **Thread-Safe Data Structures**: Use queue.Queue for producer-consumer patterns
3. **Callbacks**: Event-driven communication for UI updates
4. **Atomic Operations**: Minimize lock scope for performance

### Implementation Pattern

```python
class BatchQueue:
    def __init__(self):
        self._lock = threading.Lock()
        self.jobs: List[RenderJob] = []

    def add_job(self, job: RenderJob) -> None:
        with self._lock:
            self.jobs.append(job)
            self._save()

    def update_progress(self, job_id: int, progress: float) -> None:
        with self._lock:
            job = self.get_job(job_id)
            if job:
                job.progress = progress
                if self._on_progress:
                    self._on_progress(job, progress)
```

## Consequences

### Positive
- No race conditions on queue operations
- Consistent state across threads
- Responsive UI during rendering
- Safe concurrent file operations
- Easy to reason about thread interactions

### Negative
- Slight overhead from locking
- Need to be careful with callback timing
- Potential deadlocks if not careful with lock ordering

### Neutral
- Requires disciplined use of locks
- Callbacks must be thread-safe

## Best Practices

1. **Minimize Lock Scope**: Only lock what's necessary
2. **Avoid Nested Locks**: Prevent deadlocks
3. **Use Callbacks**: Don't update UI from worker threads directly
4. **Defensive Copying**: Return copies when sharing data between threads

## Alternatives Considered

1. **Async/Await**: Use asyncio instead of threads
   - Rejected: FFmpeg doesn't support async, would complicate code

2. **Multiprocessing**: Separate processes for isolation
   - Rejected: Overkill, more complex state management

3. **No Locking**: Just use atomic operations
   - Rejected: Not sufficient for complex state

## Implementation

See: `video_renderer/batch.py` for thread-safe BatchQueue implementation

## Related Decisions
- ADR-001: video_renderer & ramtest integration
- ADR-004: Config management
