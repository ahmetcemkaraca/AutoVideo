# Developer Care Log

## main.py run_batch() Redefinition Bug
Encountered an issue where `run_batch` was redefined later in `main.py`, overriding the main wizard logic. This caused a `NameError` crash during batch processing because the overridden `run_batch_wizard` wasn't defined in the same scope. The fix was removing the redundant, empty 3-line `def run_batch(): return run_batch_wizard()` block, which was blocking execution.

## ENOSPC Disk Space Exhaustion Bug
Encountered an ENOSPC (228) error where the disk ran out of space during long (9-hour) video batch renders. This happened because audio temp files were stored as uncompressed Wave64 (`.w64`) using `pcm_s16le`, which consumed 6.2GB per audio stream. Fixed by converting the intermediate codec to use `aac` compressed `.m4a` files at `320k` bitrates, cutting temporary size by roughly 80%.

## FFmpeg Muxer Initialization Bug
Encountered an issue where FFmpeg failed to initialize the muxer, resulting in "Requested output format 'm4a' is not a suitable output format". This caused all audio track validations to fail, raising a `ValueError: No valid audio tracks` exception. Fixed by removing the explicit `-f m4a` format flag from `audio.py` commands, since FFmpeg correctly infers the `ipod` muxer from the `.m4a` extension without it.

## Hardcoded Target FPS Bug
Encountered an issue where 60fps videos rendered much faster than expected because they were truncated during concatenation. This happened because `VideoEncoder` was initialized with a hardcoded `fps=30`, causing the frame count calculation to be halved for 60fps videos. Fixed by dynamically passing target fps into the encoder initialization.
