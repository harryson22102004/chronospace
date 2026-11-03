"""Alternative memory realities.

Procedural sketches are drawings. They are not Muse Image output and they are
not historical evidence. A live Muse Image result can be attached later, and
only the pixels inside the unobserved mask are allowed to change.
"""

from __future__ import annotations

import cv2
import numpy as np

from .pipeline import new_id, utc_now


def _unknown_mask(memory: dict, rgb_shape: tuple[int, int]) -> np.ndarray:
    from .store import _asset_path

    path = _asset_path(memory["assets"]["unknown"])
    if path.exists():
        mask = np.asarray(cv2.imread(str(path), cv2.IMREAD_GRAYSCALE))
        if mask is not None:
            return mask > 127
    return np.zeros(rgb_shape[:2], dtype=bool)


def sketch_hypothesis(memory: dict, rgb: np.ndarray, claim: str, speaker: str | None) -> dict:
    claim_l = claim.lower()
    if "book" in claim_l or "shelf" in claim_l:
        kind = "bookshelf"
        title = "Bookshelf hypothesis"
    elif "piano" in claim_l:
        kind = "piano"
        title = "Piano hypothesis"
    else:
        kind = "generic"
        title = "Hypothetical object"
    mask = _unknown_mask(memory, rgb.shape)
    if not mask.any():
        return {
            "created": False,
            "reason": (
                "This photograph has no region marked unobserved, so ChronoSpace "
                "will not paint over pixels that were actually recorded."
            ),
        }
    overlay = rgb.copy()
    ys, xs = np.where(mask)
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    if kind == "piano":
        _draw_piano(overlay, x0, y0, x1, y1)
    elif kind == "bookshelf":
        _draw_shelf(overlay, x0, y0, x1, y1)
    else:
        _draw_generic(overlay, x0, y0, x1, y1)
    plate = rgb.copy()
    plate[mask] = overlay[mask]
    # Guard: observed pixels stay identical.
    if not np.array_equal(plate[~mask], rgb[~mask]):
        raise RuntimeError("Hypothesis compositing changed pixels outside the mask.")
    rgba = np.zeros((*rgb.shape[:2], 4), np.uint8)
    rgba[..., :3] = plate
    rgba[..., 3] = np.where(mask, 255, 0).astype(np.uint8)
    hypothesis_id = new_id("hyp")
    rel = f"memories/{memory['id']}/hypotheses/{hypothesis_id}.png"
    record = {
        "id": hypothesis_id,
        "title": title,
        "claim": claim,
        "speaker": speaker,
        "status": "hypothetical",
        "kind": kind,
        "created_at": utc_now(),
        "prompt": (
            f"Illustrate a {kind} only inside the unobserved region. "
            f"Do not alter photographed pixels. Claim: {claim}"
        ),
        "generator": {
            "model_id": "procedural-hypothesis-sketch-v1",
            "provider": "local",
            "live": False,
        },
        "conflicts_with_visible_evidence": False,
        "conflict_note": (
            "The claim concerns a region whose contents are not resolved in the photograph. "
            "The sketch does not confirm the claim."
        ),
        "artifact_url": rel,
        "mask_asset": "unknown",
    }
    provenance = {
        "id": new_id("prov"),
        "entity_id": None,
        "hypothesis_id": hypothesis_id,
        "provenance_class": "generative",
        "source_photo_id": memory["photograph"]["id"],
        "source_mask_id": "unknown",
        "depth_region_id": None,
        "model": {
            "id": "procedural-hypothesis-sketch-v1",
            "provider": "local",
            "task": "illustrated_hypothesis",
        },
        "evidence": {
            "original_image_available": True,
            "mask_available": True,
            "depth_estimate_available": False,
            "generated_pixels": True,
            "human_claim": True,
        },
        "model_native_confidence": None,
        "calibration_status": "not_applicable",
        "created_at": record["created_at"],
        "notes": "Illustrated sketch inside the unobserved mask. Not a photograph and not a live image model.",
    }
    record["provenance_id"] = provenance["id"]
    return {"created": True, "record": record, "provenance": provenance, "rgba": rgba, "plate": plate}


def attach_external_image(
    memory: dict,
    rgb: np.ndarray,
    generated_rgb: np.ndarray,
    claim: str,
    speaker: str | None,
    model_id: str,
    live: bool,
) -> dict:
    """Composite an externally generated image strictly inside the unknown mask."""
    if generated_rgb.shape[:2] != rgb.shape[:2]:
        generated_rgb = cv2.resize(generated_rgb, (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_AREA)
    mask = _unknown_mask(memory, rgb.shape)
    if not mask.any():
        return {"created": False, "reason": "No unobserved mask is available to receive generated pixels."}
    plate = rgb.copy()
    plate[mask] = generated_rgb[mask]
    if not np.array_equal(plate[~mask], rgb[~mask]):
        raise RuntimeError("External composite changed photographed pixels.")
    rgba = np.zeros((*rgb.shape[:2], 4), np.uint8)
    rgba[..., :3] = plate
    rgba[..., 3] = np.where(mask, 255, 0).astype(np.uint8)
    hypothesis_id = new_id("hyp")
    rel = f"memories/{memory['id']}/hypotheses/{hypothesis_id}.png"
    record = {
        "id": hypothesis_id,
        "title": "Generated hypothesis",
        "claim": claim,
        "speaker": speaker,
        "status": "hypothetical",
        "kind": "external_image",
        "created_at": utc_now(),
        "prompt": claim,
        "generator": {"model_id": model_id, "provider": "meta" if live else "local", "live": live},
        "conflicts_with_visible_evidence": False,
        "conflict_note": "Generated pixels are confined to the unobserved mask and are not evidence.",
        "artifact_url": rel,
        "mask_asset": "unknown",
    }
    provenance = {
        "id": new_id("prov"),
        "entity_id": None,
        "hypothesis_id": hypothesis_id,
        "provenance_class": "generative",
        "source_photo_id": memory["photograph"]["id"],
        "source_mask_id": "unknown",
        "depth_region_id": None,
        "model": {"id": model_id, "provider": "meta" if live else "unknown", "task": "image_hypothesis"},
        "evidence": {
            "original_image_available": True,
            "mask_available": True,
            "depth_estimate_available": False,
            "generated_pixels": True,
            "human_claim": True,
        },
        "model_native_confidence": None,
        "calibration_status": "not_applicable",
        "created_at": record["created_at"],
        "notes": "Pixels inside the unobserved mask were replaced. Pixels outside the mask are the original photograph.",
    }
    record["provenance_id"] = provenance["id"]
    return {"created": True, "record": record, "provenance": provenance, "rgba": rgba, "plate": plate}


def _draw_piano(image: np.ndarray, x0: int, y0: int, x1: int, y1: int) -> None:
    cv2.rectangle(image, (x0, y0), (x1, y1), (88, 72, 118), -1)
    key_top = y0 + max(4, (y1 - y0) // 5)
    cv2.rectangle(image, (x0 + 2, y0 + 2), (x1 - 2, key_top), (236, 230, 220), -1)
    span = max(1, x1 - x0)
    for i in range(6):
        kx = x0 + int(span * (i + 0.5) / 6)
        cv2.rectangle(image, (kx, y0 + 2), (kx + max(2, span // 18), key_top - 4), (24, 20, 28), -1)


def _draw_shelf(image: np.ndarray, x0: int, y0: int, x1: int, y1: int) -> None:
    cv2.rectangle(image, (x0, y0), (x1, y1), (92, 70, 48), -1)
    span = max(1, y1 - y0)
    for i in range(1, 4):
        y = y0 + int(span * i / 4)
        cv2.line(image, (x0 + 2, y), (x1 - 2, y), (210, 180, 140), 2)


def _draw_generic(image: np.ndarray, x0: int, y0: int, x1: int, y1: int) -> None:
    cv2.rectangle(image, (x0, y0), (x1, y1), (120, 96, 168), -1)
    cv2.line(image, (x0, y0), (x1, y1), (230, 220, 245), 1)
