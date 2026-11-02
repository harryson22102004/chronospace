# Evaluation

Numbers below are from `python -m services.epistemic.evaluate` and `pytest` / `vitest` in this workspace. The machine-readable copy is `docs/eval-results.json`. They describe a **painted 960×640 reference** drawn by `services/epistemic/samples.py`, not a public benchmark and not a historical photograph.

## Segmentation

Intersection-over-union of the classical segmenter against the masks used to paint the reference:

| Region | IoU | Label the segmenter assigned |
| --- | ---: | --- |
| Window | 0.9455 | window |
| Curtain | 1.0000 | curtain |
| Record player | 0.6779 | record player |
| Cupboard | 0.9656 | cupboard |
| Sofa | 0.8786 | sofa |
| Lamp | 1.0000 | lamp |
| Clock | 0.5051 | clock |
| Unobserved corner | 1.0000 | unobserved corner |

The clock score is lower because the brass ring is not part of the dark disc the segmenter keeps. These IoUs will not transfer to an arbitrary photograph. SAM 3.1 was not scored here: no API key was available, and this painted set is not a SAM benchmark.

## Geometry

Depth Anything V2 Small (quantized ONNX, `depth-anything-v2-small-q4`) took **293.58 ms** on CPU for this image. Output range was 0.379 to 5.675. Calibration status: not calibrated.

Spearman correlation against “lower in the frame is closer” (a property of this drawing, not of the world):

- Depth Anything V2: **0.5255**
- Classical ground-plane prior: **0.9955** (the prior is mostly that row cue, plus a small luminance term)

A separate synthetic probe, not this table, put a higher network value on a foreground chair than on a small bright window. The viewer treats higher as closer on that basis.

## Reconstruction

At the source view the mesh is textured with the photograph, so the maximum absolute channel difference versus the input is **0**. That is fidelity to the input view by construction, not a novel-view score. PSNR, SSIM, and LPIPS against a second photograph were not computed; no such photograph exists.

An 18-pixel horizontal parallax warp (destination holes inside the frame, border excluded):

| Depth field | Unfilled fraction |
| --- | ---: |
| Depth Anything V2 | 0.0056 |
| Same depth, each segment replaced by its median | 0.0050 |
| Ground-plane prior | 0.0033 |

On this smooth painted image, flattening segments does not remove a meaningful number of holes. The comparison is reported because it was measured, not because one method wins.

End-to-end local pipeline: **0.879 s**. Saved JPEG: **34,722 bytes**.

## Provenance

12 of 12 entities had both an observed record and a vision-estimated record (`lineage_completeness` 1.0 on this run). A piano sketch changed no pixel outside the unknown mask (`hypothesis_preserves_pixels_outside_mask: true`). No generative model ran unless a hypothesis was requested.

## Agent

`tests/test_engine.py` checks five questions on the painted interior:

- “Show me the old record player.” focuses the record-player entity and says the depth scale is not calibrated.
- “What is behind this cupboard?” says the dark region’s contents are unknown and does not name a piano.
- “My grandmother remembers a piano being next to the window.” stores testimony, says the photograph neither shows the piano nor proves it was absent, and offers a hypothesis.
- A request for meters is refused.
- A request for the year is refused when no capture time is stored.

## Not measured

Live Meta latency and cost. Novel-view perceptual metrics. Calibrated probabilities. Browser frame rate (the viewer prints a frame counter; it is not in this table).
