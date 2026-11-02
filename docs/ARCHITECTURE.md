# Architecture

ChronoSpace is two processes that share a `data/` directory.

- **Next.js** (`app/`, port 43123) is the product surface: gallery, import, the Three.js memory, Truth Lens, audit, graph, and alternative realities. It also holds every Meta API call, so keys stay on the server.
- **FastAPI** (`services/epistemic/`, port 8742) is the epistemic engine: image validation, Depth Anything V2, classical segmentation, provenance, the tool executor, and procedural hypotheses.

The browser never calls Meta and never calls the vision port directly. `/api/*` proxies the vision service and, when `MODEL_API_KEY` is set and the upload consented, adds SAM 3.1, Muse Spark, and Muse Image.

## Reconstruction

1. The upload is decoded, optionally read for EXIF `DateTimeOriginal` (tag 36867), transposed, resized so the long edge is at most 1600 px, and re-encoded as JPEG without an EXIF segment.
2. Regions come from Lab k-means, connected components, one dark Hough circle, and shape rules (`chromatic-heuristic-v1`, `hough-circle-on-cabinet-v1`). Labels are heuristics.
3. Relative depth comes from Depth Anything V2 Small, quantized ONNX (`depth-anything-v2-small-q4`), ImageNet-normalized at 518². If the checkpoint is missing, a ground-plane prior is used and named as such.
4. Larger network outputs are treated as closer. That direction was checked on a synthetic interior probe (a near chair scored higher than a far window) and is **not** a metric calibration.
5. Each entity receives an observed provenance record (the pixels) and a vision-estimated record (the mask, the label, the depth sample). Dark edge regions can be `content_status: unknown`: the pixels were photographed and the contents were not resolved.
6. No fill is generated during the base reconstruction. Disocclusion from camera motion is a renderer limit, not a new observation.

## Viewer

A subdivided plane is displaced along view depth by the normalized depth image. Orbit is clamped to roughly ±24° of azimuth and a short dolly. The original lens sets displacement to zero, so the photograph is shown flat. Truth Lens modes recolor the same mesh; they do not swap in a different scene.

Selection reads an entity-id PNG in the browser. The agent returns `focus_camera` and `highlight` actions with the entity’s texture UV, and the camera target eases toward that point.

## Agent

Tools are implemented in `services/epistemic/agent.py` and are the only writers of testimony and hypotheses. The narration is assembled from tool results.

- Without a key, `local-evidence-orchestrator` chooses the tools from the wording of the question.
- With a key and consent, Muse Spark 1.3 may choose the same tools. Their results are executed, then summarized from those results. Free-form model text is shown as commentary, not as evidence.
- A live Meta badge is stored only on an invocation with `live: true` and `status: succeeded`.

## Branches

An alternative reality is a hypothesis record. The procedural sketcher (`procedural-hypothesis-sketch-v1`) draws inside the unknown mask. Muse Image, when it actually returns an image, is composited with the same mask. Pixels outside the mask are required to stay identical to the photograph.

## What is intentionally absent

Single-view 3D Gaussian Splatting is not claimed. No splat file is produced, and `@sparkjsdev/spark` is not mounted. Muse Spark Open (816B MoE) is not served. There is no trained confidence calibrator.
