# ChronoSpace

A photograph is a window into a world. ChronoSpace lets you step inside while showing you what is real, estimated, and imagined.

Upload a picture. The local engine estimates relative depth with Depth Anything V2 Small, splits regions with a classical segmenter, and opens a clamped 3D view of that same photograph. Every region keeps a provenance record: observed pixels, vision estimates, generated pixels, or human testimony. A Truth Lens recolours the mesh to match. A spatial agent can only answer from those records. An alternative reality is a hypothesis, clipped so it cannot repaint the original.

If `MODEL_API_KEY` is set and the importer consents, the server calls Meta’s Model API: SAM 3.1, Muse Spark 1.3, Muse Image, and Muse Voice Transcribe. A live badge appears only after a successful call. Without a key, the product still runs and says so.

The two memories created on first launch are **painted references**, not historical photographs. Their vision output is from the local models.

## Run

```bash
bash scripts/setup.sh
cp .env.example .env
npm run dev
```

- App: http://127.0.0.1:43123
- Vision service: http://127.0.0.1:8742/health

`scripts/setup.sh` creates a virtualenv, installs Python and Node dependencies, and downloads the 27 MB Depth Anything V2 Small quantized ONNX file from `onnx-community/depth-anything-v2-small`.

```bash
npm test
npm run evaluate
```

## Environment

| Variable | Role |
| --- | --- |
| `MODEL_API_KEY` | Meta Model API bearer token. Optional. |
| `VISION_URL` | Defaults to `http://127.0.0.1:8742`. |
| `VISION_HOST` | Production vision bind address. Defaults to `127.0.0.1`. |
| `DEPTH_MODEL_PATH` | ONNX checkpoint. |
| `CHRONOSPACE_DATA` | Memory store. Defaults to `data/`. |

Keys stay in the Next.js server. The browser does not see them.

## Production

```bash
npm run build
node scripts/start.mjs
```

The Node server and the Python vision service both have to stay up. A static host that cannot run ONNX Runtime will not reconstruct new photographs. See `Dockerfile`.

## Documents

- [Architecture](docs/ARCHITECTURE.md)
- [Meta integration](docs/META_INTEGRATION.md)
- [Evaluation](docs/EVALUATION.md)
- [Limitations](docs/LIMITATIONS.md)
- [Research notes](docs/RESEARCH.md)
- [Three-minute demo](docs/DEMO_SCRIPT.md)
- [Readiness](docs/READINESS.md)

## Layout

```
app/                    Next.js UI and API routes
components/living-scene.tsx
services/epistemic/     depth, segmentation, provenance, agent
tests/                  pytest and SAM parser tests
```
