"""Build a memory: photograph, regions, relative depth, provenance."""

from __future__ import annotations

import hashlib
import io
import uuid
from datetime import datetime, timezone
from typing import Callable

import cv2
import numpy as np
from PIL import Image, ImageOps

from .config import MAX_EDGE
from .depth import estimate_depth, surface_normals
from .segment import Region, segment_image

Emit = Callable[[str, str, str], None]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _noop(stage: str, status: str, detail: str) -> None:
    return None


def read_upload(data: bytes, use_capture_time: bool) -> tuple[np.ndarray, str | None, str]:
    """Return RGB, optional EXIF time, and a reliability token.

    EXIF is read only when the user authorized it, then dropped. The saved
    image is re-encoded without a metadata segment.
    """
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except Exception as exc:  # noqa: BLE001
        raise ValueError("The file is not a readable JPEG, PNG, or WebP image.") from exc
    capture = None
    reliability = "unknown"
    if use_capture_time:
        exif = image.getexif()
        raw = None
        if exif:
            raw = exif.get(36867) or exif.get(306)
        if isinstance(raw, str) and raw.strip():
            capture = raw.strip()
            reliability = "exif"
    image = ImageOps.exif_transpose(image).convert("RGB")
    w, h = image.size
    edge = max(w, h)
    if edge > MAX_EDGE:
        scale = MAX_EDGE / edge
        image = image.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    if min(image.size) < 64:
        raise ValueError("The image is smaller than 64 pixels on one side.")
    rgb = np.asarray(image, dtype=np.uint8)
    return rgb, capture, reliability


def _sha256(rgb: np.ndarray) -> str:
    return hashlib.sha256(rgb.tobytes()).hexdigest()


def _centroid_uv(mask: np.ndarray) -> list[float]:
    ys, xs = np.where(mask)
    h, w = mask.shape
    if len(xs) == 0:
        return [0.5, 0.5]
    x = float(xs.mean()) / max(w - 1, 1)
    y = float(ys.mean()) / max(h - 1, 1)
    return [round(x, 4), round(1 - y, 4)]


def _audio_profile(labels: list[str]) -> dict:
    elements = ["room tone"]
    if "sky" in labels or "foliage" in labels:
        elements = ["wind", "distant birds"]
    if "window" in labels and "sky" not in labels:
        elements.extend(["wind", "distant birds"])
    if "clock" in labels:
        elements.append("clock")
    if any("fire" in label for label in labels):
        elements.append("fireplace")
    # Stable, unique order.
    ordered = []
    for item in elements:
        if item not in ordered:
            ordered.append(item)
    return {
        "elements": ordered,
        "origin": "rule_map",
        "model_id": "scene-audio-rules-v1",
        "note": (
            "Sound elements are chosen from labels by a fixed rule list and "
            "synthesized in the browser. This is not a reconstruction of the room's acoustics."
        ),
    }


def _summary(labels: list[str], depth_note: str) -> str:
    named = [label for label in labels if label not in {"region", "wall", "floor"}]
    if not named:
        body = "The segmenter found broad regions and did not name a specific object."
    else:
        body = "Named regions, from a classical segmenter: " + ", ".join(named) + "."
    return (
        body
        + " Depth is relative and uncalibrated. "
        + depth_note
    )


def _title_from(labels: list[str]) -> str:
    if "record player" in labels and "window" in labels:
        return "Interior with a record player"
    if "record player" in labels:
        return "Record player"
    named = [label for label in labels if label not in {"region", "wall", "floor"}]
    if named:
        return named[0].capitalize() + " — photograph"
    return "Untitled photograph"


def _located_near(entities: list[dict]) -> list[dict]:
    links = []
    for i, a in enumerate(entities):
        for b in entities[i + 1 :]:
            ax, ay = a["centroid_uv"]
            bx, by = b["centroid_uv"]
            dist = float(np.hypot(ax - bx, ay - by))
            if dist < 0.34 and a["label"] not in {"wall", "floor"} and b["label"] not in {"wall", "floor"}:
                links.append(
                    {
                        "id": new_id("rel"),
                        "type": "located_near",
                        "source_id": a["id"],
                        "target_id": b["id"],
                        "status": "estimated",
                        "note": (
                            f"Image-plane centroids are {dist:.2f} apart on a 0–1 scale. "
                            "This is not a measured room distance."
                        ),
                    }
                )
    return links


def build_memory(
    rgb: np.ndarray,
    *,
    consent: dict,
    capture_time: str | None,
    capture_time_reliability: str,
    sample: bool = False,
    sample_note: str | None = None,
    title: str | None = None,
    emit: Emit = _noop,
) -> tuple[dict, dict[str, np.ndarray]]:
    """Return the memory record and a dict of image arrays to save."""
    started = utc_now()
    emit("photograph_analysis", "running", "Reading the photograph and stripping metadata.")
    height, width = rgb.shape[:2]
    photo_id = new_id("photo")
    memory_id = new_id("mem")
    digest = _sha256(rgb)

    emit("object_segmentation", "running", "Quantizing color and applying shape rules.")
    seg_started = datetime.now(timezone.utc)
    regions = segment_image(rgb)
    seg_ms = (datetime.now(timezone.utc) - seg_started).total_seconds() * 1000
    emit(
        "object_segmentation",
        "succeeded",
        f"{len(regions)} regions from the classical segmenter.",
    )

    emit("depth_estimation", "running", "Estimating relative depth.")
    depth = estimate_depth(rgb)
    normals = surface_normals(depth.normalized)
    emit("depth_estimation", "succeeded", depth.note)

    emit("semantic_reconstruction", "running", "Attaching depth to each region.")
    entities, entity_map, unknown, motion, entity_masks = _entities(
        regions, depth.normalized, depth.disparity
    )
    emit("semantic_reconstruction", "succeeded", f"{len(entities)} entities placed on the depth field.")

    emit("generative_completion", "running", "Checking for pixels that were not in the photograph.")
    generated = np.zeros((height, width), np.uint8)
    emit(
        "generative_completion",
        "succeeded",
        "No pixels were generated. Unobserved content stays unmarked rather than filled in.",
    )

    grad = np.hypot(
        cv2.Sobel(depth.normalized, cv2.CV_32F, 1, 0, ksize=3),
        cv2.Sobel(depth.normalized, cv2.CV_32F, 0, 1, ksize=3),
    )
    cutoff = float(np.percentile(grad, 94))
    disocclusion = (grad >= cutoff).astype(np.uint8) * 255

    emit("evidence_graph", "running", "Writing provenance for pixels, masks, and depth.")
    provenances, invocations = _provenance(
        entities, photo_id, depth, seg_ms, started
    )
    labels = [entity["label"] for entity in entities]
    relationships = [
        {
            "id": new_id("rel"),
            "type": "appears_in",
            "source_id": entity["id"],
            "target_id": photo_id,
            "status": "observed",
            "note": "The entity's pixels come from this photograph.",
        }
        for entity in entities
    ]
    relationships.extend(_located_near(entities))
    emit("evidence_graph", "succeeded", f"{len(provenances)} provenance records.")

    emit("spatial_rendering", "running", "Packing depth, masks, and normals for the viewer.")
    assets = {
        "photo": f"memories/{memory_id}/photo.jpg",
        "depth": f"memories/{memory_id}/depth.png",
        "normals": f"memories/{memory_id}/normals.png",
        "entity_ids": f"memories/{memory_id}/entity_ids.png",
        "unknown": f"memories/{memory_id}/unknown.png",
        "generated": f"memories/{memory_id}/generated.png",
        "testimony": f"memories/{memory_id}/testimony.png",
        "motion": f"memories/{memory_id}/motion.png",
        "disocclusion": f"memories/{memory_id}/disocclusion.png",
        "hypothesis": f"memories/{memory_id}/hypothesis.png",
    }
    testimony = np.zeros((height, width), np.uint8)
    hypothesis = np.zeros((height, width, 4), np.uint8)
    images = {
        "photo.jpg": rgb,
        "depth.png": (depth.normalized * 255).astype(np.uint8),
        "normals.png": normals,
        "entity_ids.png": entity_map,
        "unknown.png": unknown,
        "generated.png": generated,
        "testimony.png": testimony,
        "motion.png": motion,
        "disocclusion.png": disocclusion,
        "hypothesis.png": hypothesis,
    }
    for entity in entities:
        mask_name = f"masks/{entity['id']}.png"
        images[mask_name] = entity_masks[entity["id"]]
        entity["mask_url"] = f"memories/{memory_id}/{mask_name}"
    emit("spatial_rendering", "succeeded", "The viewer can displace the photograph by the depth field.")

    description = _summary(labels, depth.note)
    memory = {
        "id": memory_id,
        "title": title or _title_from(labels),
        "created_at": started,
        "sample": sample,
        "sample_note": sample_note,
        "consent": consent,
        "photograph": {
            "id": photo_id,
            "width": width,
            "height": height,
            "sha256": digest,
            "capture_time": capture_time,
            "capture_time_reliability": capture_time_reliability,
            "url": assets["photo"],
        },
        "depth": {
            "model_id": depth.model_id,
            "provider": depth.provider,
            "note": depth.note,
            "disparity_min": float(depth.disparity.min()),
            "disparity_max": float(depth.disparity.max()),
            "closer": "higher",
            "calibration_status": "not_calibrated",
            "duration_ms": round(depth.duration_ms, 2),
            "url": assets["depth"],
            "normals_url": assets["normals"],
        },
        "segmentation": {
            "model_id": "chromatic-heuristic-v1",
            "provider": "local",
            "live_meta": False,
            "note": (
                "Regions come from Lab quantization, connected components, and shape rules. "
                "They are not SAM 3.1 masks unless a later invocation says so."
            ),
        },
        "scene_description": {"text": description, "origin": "template", "model_id": None},
        "audio_profile": _audio_profile(labels),
        "entities": entities,
        "relationships": relationships,
        "provenances": provenances,
        "testimonies": [],
        "hypotheses": [],
        "active_hypothesis_id": None,
        "invocations": invocations,
        "assets": assets,
        "links": [],
    }
    return memory, images


def _entities(regions: list[Region], normalized: np.ndarray, disparity: np.ndarray):
    h, w = normalized.shape
    entity_map = np.zeros((h, w), np.uint8)
    unknown = np.zeros((h, w), np.uint8)
    motion = np.zeros((h, w), np.uint8)
    entities = []
    entity_masks: dict[str, np.ndarray] = {}
    for index, region in enumerate(regions[:200]):
        eid = new_id("ent")
        value = index + 1
        entity_map[region.mask] = value
        if region.content_status == "unknown":
            unknown[region.mask] = 255
        if region.animation in {"curtain", "foliage"}:
            motion[region.mask] = 255
        med_n = float(np.median(normalized[region.mask])) if region.mask.any() else 0.0
        med_d = float(np.median(disparity[region.mask])) if region.mask.any() else 0.0
        x, y, bw, bh = region.bbox
        entities.append(
            {
                "id": eid,
                "index": value,
                "label": region.label,
                "label_origin": region.label_origin,
                "content_status": region.content_status,
                "animation": region.animation,
                "classifier_note": region.classifier_note,
                "bbox": {"x": x, "y": y, "w": bw, "h": bh},
                "bbox_norm": {
                    "x": round(x / w, 4),
                    "y": round(y / h, 4),
                    "w": round(bw / w, 4),
                    "h": round(bh / h, 4),
                },
                "centroid_uv": _centroid_uv(region.mask),
                "median_normalized_depth": round(med_n, 4),
                "median_disparity": round(med_d, 4),
                "area_fraction": round(float(region.mask.mean()), 4),
                "mask_url": "",
                "provenance_ids": [],
            }
        )
        entity_masks[eid] = (region.mask.astype(np.uint8) * 255)
    return entities, entity_map, unknown, motion, entity_masks


def _provenance(entities: list[dict], photo_id: str, depth, seg_ms: float, started: str):
    provenances = []
    now = utc_now()
    depth_prov = {
        "id": new_id("prov"),
        "entity_id": None,
        "provenance_class": "vision_estimated",
        "source_photo_id": photo_id,
        "source_mask_id": None,
        "depth_region_id": "depth_field",
        "model": {
            "id": depth.model_id,
            "provider": depth.provider,
            "task": "relative_depth",
        },
        "evidence": {
            "original_image_available": True,
            "mask_available": False,
            "depth_estimate_available": True,
            "generated_pixels": False,
            "human_claim": False,
        },
        "model_native_confidence": None,
        "calibration_status": "not_calibrated",
        "created_at": now,
        "notes": depth.note,
    }
    provenances.append(depth_prov)
    for entity in entities:
        observed = {
            "id": new_id("prov"),
            "entity_id": entity["id"],
            "provenance_class": "observed",
            "source_photo_id": photo_id,
            "source_mask_id": entity["id"],
            "depth_region_id": None,
            "model": None,
            "evidence": {
                "original_image_available": True,
                "mask_available": True,
                "depth_estimate_available": False,
                "generated_pixels": False,
                "human_claim": False,
            },
            "model_native_confidence": None,
            "calibration_status": "not_applicable",
            "created_at": now,
            "notes": "Pixels inside this mask are copied from the uploaded photograph.",
        }
        estimated = {
            "id": new_id("prov"),
            "entity_id": entity["id"],
            "provenance_class": "vision_estimated",
            "source_photo_id": photo_id,
            "source_mask_id": entity["id"],
            "depth_region_id": entity["id"],
            "model": {
                "id": entity["label_origin"],
                "provider": "local",
                "task": "segmentation_and_relative_depth_sample",
            },
            "evidence": {
                "original_image_available": True,
                "mask_available": True,
                "depth_estimate_available": True,
                "generated_pixels": False,
                "human_claim": False,
            },
            "model_native_confidence": None,
            "calibration_status": "not_calibrated",
            "created_at": now,
            "notes": entity["classifier_note"]
            + (
                " The dark pixels are visible, but the object that may occupy this space was not resolved."
                if entity["content_status"] == "unknown"
                else ""
            ),
        }
        entity["provenance_ids"] = [observed["id"], estimated["id"]]
        provenances.extend([observed, estimated])
    invocations = [
        {
            "id": new_id("inv"),
            "model_id": depth.model_id,
            "provider": depth.provider,
            "task": "relative_depth",
            "status": "succeeded",
            "live": False,
            "started_at": started,
            "ended_at": now,
            "duration_ms": round(depth.duration_ms, 2),
            "output_summary": depth.note,
            "error": None,
        },
        {
            "id": new_id("inv"),
            "model_id": "chromatic-heuristic-v1",
            "provider": "local",
            "task": "segmentation",
            "status": "succeeded",
            "live": False,
            "started_at": started,
            "ended_at": now,
            "duration_ms": round(seg_ms, 2),
            "output_summary": f"{len(entities)} regions. No Meta model was called.",
            "error": None,
        },
    ]
    return provenances, invocations
