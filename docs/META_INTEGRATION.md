# Meta integration

Checked against the public Model API docs (fetched for this build):

- Models: https://dev.meta.ai/docs/models
- Responses: https://dev.meta.ai/docs/protocols/responses
- SAM overview and output grammar: https://dev.meta.ai/docs/sam/overview and https://dev.meta.ai/docs/sam/reading-segmentation
- Client library: `@meta-sam/parser` (documented at https://dev.meta.ai/docs/sam/client-libraries)
- Image generation: https://dev.meta.ai/docs/image-generation
- Voice file transcription: https://dev.meta.ai/docs/speech-to-text and https://dev.meta.ai/docs/api-reference/voice/transcribe

Base URL: `https://api.meta.ai/v1`. Auth: `Authorization: Bearer $MODEL_API_KEY`.

| Model id | Endpoint | Use in ChronoSpace |
| --- | --- | --- |
| `sam-3.1` | `POST /v1/responses`, streamed | Noun-phrase segmentation. `metadata.mask_encoding = one_bit`, `include_confidence = true`. |
| `muse-spark-1.3` | `POST /v1/responses` | Scene JSON (validated before use) and spatial tool selection. |
| `muse-image-1.0` | `POST /v1/responses` | A hypothetical image, then masked back to the unobserved region. |
| `muse-voice-transcribe-1.0` | `POST /v1/asr/transcribe` | Multipart `request` JSON plus mono 16-bit PCM WAV at 16 kHz, mode `PUSH_TO_TALK`. |

SAM text is parsed with `@meta-sam/parser` (`parseImageStream`, `decodeMaskToRaster`). Tests cover sparse object ids, half-open boxes, mask dimensions, an empty lane, and a truncated payload. A truncated mask is dropped; it is not repaired.

`include_confidence` values are stored as model-native scores with `calibration_status: not_calibrated`. Missing `c` is stored as absent, not as zero.

Muse Spark scene text must parse as JSON `{ title?, summary, audio[] }` with `summary` between 8 and 1800 characters and audio names from a fixed list. Anything else is discarded and the invocation is `failed`, not live.

Muse Spark Open was not integrated. The published checkpoint is an 816B-parameter mixture-of-experts model. This machine has no GPU and no partner key, and the project does not claim a hackathon inference run.

This environment had no `MODEL_API_KEY`, so no live latency or cost was measured. The UI shows “Local models only” until a real call succeeds.
