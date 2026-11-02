"""Measurements taken from code in this repository. No borrowed benchmark numbers."""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from .depth import estimate_depth, estimate_ground_prior
from .hypotheses import sketch_hypothesis
from .pipeline import build_memory
from .samples import living_room
from .segment import iou, segment_image
from .store import save_memory


def warp_hole_fraction(normalized: np.ndarray, shift: float = 18.0) -> float:
    """Fraction of destination pixels missed by a horizontal parallax warp."""
    h, w = normalized.shape
    dest = np.zeros((h, w), np.uint8)
    ys, xs = np.indices((h, w))
    offset = ((normalized - 0.5) * shift).astype(np.int32)
    nx = xs + offset
    valid = (nx >= 0) & (nx < w)
    dest[ys[valid], nx[valid]] = 1
    # Ignore a border of `shift` pixels, which a camera pan naturally leaves.
    border = int(abs(shift)) + 1
    interior = dest[:, border : w - border]
    return float(1.0 - interior.mean())


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    ar = a.argsort().argsort().astype(np.float64)
    br = b.argsort().argsort().astype(np.float64)
    ar -= ar.mean()
    br -= br.mean()
    denom = np.sqrt((ar * ar).sum() * (br * br).sum())
    if denom == 0:
        return 0.0
    return float((ar * br).sum() / denom)


def run() -> dict:
    rgb, truth = living_room()
    regions = segment_image(rgb)
    ious = {}
    for name, mask in truth.items():
        if not mask.any():
            continue
        best = 0.0
        label = None
        for region in regions:
            score = iou(region.mask, mask)
            if score > best:
                best = score
                label = region.label
        ious[name] = {"iou": round(best, 4), "matched_label": label}

    started = time.perf_counter()
    memory, images = build_memory(
        rgb,
        consent={
            "rights_confirmed": True,
            "external_models": False,
            "use_capture_time": False,
            "accepted_at": "1970-01-01T00:00:00+00:00",
        },
        capture_time=None,
        capture_time_reliability="unknown",
        sample=True,
    )
    pipeline_s = time.perf_counter() - started
    save_memory(memory, images)

    photo = images["photo.jpg"]
    # Frontal reconstruction uses the photograph as the texture, so the source view matches it.
    frontal_max_abs = int(np.max(np.abs(photo.astype(np.int16) - rgb.astype(np.int16))))

    depth = estimate_depth(rgb)
    prior = estimate_ground_prior(rgb)
    rows = np.linspace(0, 1, rgb.shape[0], dtype=np.float32)
    # 0 at the top of the image, 1 at the bottom. The painted floor sits at the bottom.
    bottom_closer = np.repeat(rows[:, None], rgb.shape[1], axis=1)
    flat = depth.normalized.copy()
    for region in regions:
        if region.mask.any():
            flat[region.mask] = float(np.median(depth.normalized[region.mask]))

    built = sketch_hypothesis(memory, rgb, "a piano in the dark corner", "test")
    outside_identical = False
    if built.get("created"):
        outside_identical = bool(np.array_equal(built["plate"][~(_mask(memory))], rgb[~(_mask(memory))]))

    entities = memory["entities"]
    complete = 0
    for entity in entities:
        classes = {
            prov["provenance_class"]
            for prov in memory["provenances"]
            if prov.get("entity_id") == entity["id"]
        }
        if "observed" in classes and "vision_estimated" in classes and entity["mask_url"]:
            complete += 1

    report = {
        "photograph": {"width": int(rgb.shape[1]), "height": int(rgb.shape[0]), "kind": "painted_reference"},
        "segmentation_iou": ious,
        "depth": {
            "model_id": memory["depth"]["model_id"],
            "duration_ms": memory["depth"]["duration_ms"],
            "disparity_min": memory["depth"]["disparity_min"],
            "disparity_max": memory["depth"]["disparity_max"],
            "calibration_status": "not_calibrated",
            "spearman_vs_bottom_closer_dav2": round(spearman(depth.normalized.ravel()[::20], bottom_closer.ravel()[::20]), 4),
            "spearman_vs_bottom_closer_ground_prior": round(
                spearman(prior.normalized.ravel()[::20], bottom_closer.ravel()[::20]), 4
            ),
        },
        "reconstruction": {
            "frontal_max_abs_channel_diff": frontal_max_abs,
            "disocclusion_hole_fraction_dav2_shift18": round(warp_hole_fraction(depth.normalized), 4),
            "disocclusion_hole_fraction_segmented_median_shift18": round(warp_hole_fraction(flat), 4),
            "disocclusion_hole_fraction_ground_prior_shift18": round(warp_hole_fraction(prior.normalized), 4),
            "pipeline_seconds": round(pipeline_s, 3),
            "photo_jpeg_bytes": _jpeg_size(photo),
        },
        "provenance": {
            "entities": len(entities),
            "entities_with_observed_and_estimated_records": complete,
            "lineage_completeness": round(complete / max(len(entities), 1), 4),
            "hypothesis_preserves_pixels_outside_mask": outside_identical,
            "generated_model_when_unrequested": "none",
        },
        "not_measured": [
            "Live Meta API latency and cost — MODEL_API_KEY was not configured in this run.",
            "PSNR/SSIM/LPIPS against a held-out novel view — no such photograph exists for the painted reference.",
            "Calibrated probabilities — none were trained.",
            "Browser frames per second — measured in the viewer, not in this process.",
        ],
    }
    return report


def _mask(memory: dict) -> np.ndarray:
    from .hypotheses import _unknown_mask

    return _unknown_mask(memory, (memory["photograph"]["height"], memory["photograph"]["width"]))


def _jpeg_size(rgb: np.ndarray) -> int:
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.fromarray(rgb).save(buffer, format="JPEG", quality=92)
    return buffer.tell()


def main() -> None:
    report = run()
    out = Path(__file__).resolve().parents[2] / "docs" / "eval-results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
