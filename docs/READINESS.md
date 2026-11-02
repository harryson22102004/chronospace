# Readiness

| Check | State |
| --- | --- |
| Photograph upload with type and size checks | Implemented. Invalid bytes raise a readable error. |
| EXIF stripped unless the user allows a capture time | Tested. |
| Depth Anything V2 Small ONNX on CPU | Running. 293.58 ms on the painted reference. |
| Fallback if the ONNX file is missing | `classical-ground-prior-v1`, named as such. |
| Classical segmentation with a disclosed IoU table | Measured in `docs/EVALUATION.md`. |
| SAM 3.1 client, official parser, live badge only after success | Implemented. Not executed here: no API key. |
| Muse Spark scene JSON validation and tool selection | Implemented. Not executed here. |
| Muse Image hypothesis clipped to the unknown mask | Implemented. Not executed here. |
| Voice: browser WAV, then `muse-voice-transcribe-1.0`, confirm before testimony | Implemented. Not executed here. |
| Interactive depth mesh, clamped camera, Truth Lens | Implemented in the viewer. |
| Provenance on every entity | 12/12 on the painted reference. |
| Grounded agent, including refusals | Covered by `tests/test_engine.py`. |
| Alternative realities that do not overwrite the photo | Mask test passed. |
| Cross-photo proposal, not an identity claim | Histogram correlation stored as a cue. |
| Timeline only with two real capture times | Implemented. |
| Gaussian splatting | Not claimed. |
| Muse Spark Open | Not run. |
| Tests | `vitest` 5 passed, `pytest` 3 passed, on this machine. |
| Browser pass | See the session note in the README after the dev server is up. |

Deadline context used while building: 4 November 2026, 9:00 PM America/New_York.
