"""Attach real Meta outputs onto a memory. Nothing here invents a response."""

from __future__ import annotations

import base64
import io

import numpy as np
from PIL import Image

from .pipeline import new_id, utc_now
from .segment import iou
from .store import update_memory, write_asset
from .store import _asset_path


def _load_gray(rel: str) -> np.ndarray:
    image = np.asarray(Image.open(_asset_path(rel)).convert("L"))
    return image


def attach_scene(memory: dict, summary: str, title: str | None, audio: list[str], invocation: dict) -> dict:
    text = summary.strip()
    if not text:
        raise ValueError("Muse Spark returned an empty scene summary.")
    memory["scene_description"] = {
        "text": text,
        "origin": "muse-spark-1.3",
        "model_id": "muse-spark-1.3",
    }
    if title and title.strip():
        memory["title"] = title.strip()
    if audio:
        cleaned = [item.strip() for item in audio if isinstance(item, str) and item.strip()]
        if cleaned:
            memory["audio_profile"]["elements"] = cleaned
            memory["audio_profile"]["origin"] = "muse-spark-1.3"
            memory["audio_profile"]["model_id"] = "muse-spark-1.3"
            memory["audio_profile"]["note"] = (
                "Muse Spark chose these element names from the photograph. "
                "The browser synthesizes them. This is not a recording and not acoustic reconstruction."
            )
    memory["invocations"].append(invocation)
    update_memory(memory)
    return memory


def attach_sam(
    memory: dict,
    *,
    prompt: str,
    object_id: str,
    mask_png: bytes,
    confidence: float | None,
    invocation: dict,
) -> dict:
    mask_img = Image.open(io.BytesIO(mask_png)).convert("L")
    width = memory["photograph"]["width"]
    height = memory["photograph"]["height"]
    if mask_img.size != (width, height):
        mask_img = mask_img.resize((width, height), Image.Resampling.NEAREST)
    mask = np.asarray(mask_img) > 127
    if int(mask.sum()) < 16:
        invocation = {**invocation, "status": "succeeded", "output_summary": f"SAM prompt '{prompt}' returned an empty mask."}
        memory["invocations"].append(invocation)
        update_memory(memory)
        return memory

    entity_map = _load_gray(memory["assets"]["entity_ids"])
    best = None
    best_score = 0.0
    for entity in memory["entities"]:
        existing = entity_map == entity["index"]
        score = iou(existing, mask)
        label_match = entity["label"] in prompt.lower() or prompt.lower() in entity["label"]
        if label_match:
            score += 0.15
        if score > best_score:
            best, best_score = entity, score

    confidence_record = None
    if confidence is not None and 0 <= confidence <= 1:
        confidence_record = {
            "value": confidence,
            "origin": "sam-3.1 metadata include_confidence",
            "calibration_status": "not_calibrated",
        }

    if best is not None and best_score >= 0.2:
        entity = best
        entity["label_origin"] = "sam-3.1"
        entity["classifier_note"] = (
            f"Mask from SAM 3.1 for the prompt '{prompt}', object id {object_id}. "
            "The box and mask are model output, not a survey."
        )
        if confidence_record:
            entity["model_native_confidence"] = confidence_record
        entity_map[entity_map == entity["index"]] = 0
        entity_map[mask] = entity["index"]
        ys, xs = np.where(mask)
        entity["bbox"] = {
            "x": int(xs.min()),
            "y": int(ys.min()),
            "w": int(xs.max() - xs.min() + 1),
            "h": int(ys.max() - ys.min() + 1),
        }
        entity["centroid_uv"] = [
            round(float(xs.mean()) / max(width - 1, 1), 4),
            round(1 - float(ys.mean()) / max(height - 1, 1), 4),
        ]
        entity["area_fraction"] = round(float(mask.mean()), 4)
        write_asset(memory["id"], f"masks/{entity['id']}.png", (mask.astype(np.uint8) * 255))
        for prov in memory["provenances"]:
            if prov.get("entity_id") == entity["id"] and prov["provenance_class"] == "vision_estimated":
                prov["model"] = {"id": "sam-3.1", "provider": "meta", "task": "segmentation"}
                prov["model_native_confidence"] = confidence_record
                prov["notes"] = entity["classifier_note"]
                prov["calibration_status"] = "not_calibrated"
    else:
        index = max(entity["index"] for entity in memory["entities"]) + 1
        if index > 255:
            raise ValueError("The entity map is full.")
        entity_id = new_id("ent")
        entity_map[mask] = index
        ys, xs = np.where(mask)
        entity = {
            "id": entity_id,
            "index": index,
            "label": prompt.strip() or "sam object",
            "label_origin": "sam-3.1",
            "content_status": "observed",
            "animation": None,
            "classifier_note": f"SAM 3.1 object {object_id} for prompt '{prompt}', with no matching local region.",
            "bbox": {
                "x": int(xs.min()),
                "y": int(ys.min()),
                "w": int(xs.max() - xs.min() + 1),
                "h": int(ys.max() - ys.min() + 1),
            },
            "bbox_norm": {},
            "centroid_uv": [
                round(float(xs.mean()) / max(width - 1, 1), 4),
                round(1 - float(ys.mean()) / max(height - 1, 1), 4),
            ],
            "median_normalized_depth": None,
            "median_disparity": None,
            "area_fraction": round(float(mask.mean()), 4),
            "mask_url": f"memories/{memory['id']}/masks/{entity_id}.png",
            "provenance_ids": [],
        }
        if confidence_record:
            entity["model_native_confidence"] = confidence_record
        x, y, w, h = entity["bbox"]["x"], entity["bbox"]["y"], entity["bbox"]["w"], entity["bbox"]["h"]
        entity["bbox_norm"] = {
            "x": round(x / width, 4),
            "y": round(y / height, 4),
            "w": round(w / width, 4),
            "h": round(h / height, 4),
        }
        observed = {
            "id": new_id("prov"),
            "entity_id": entity_id,
            "provenance_class": "observed",
            "source_photo_id": memory["photograph"]["id"],
            "source_mask_id": entity_id,
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
            "created_at": utc_now(),
            "notes": "Pixels inside the SAM mask are from the uploaded photograph.",
        }
        estimated = {
            "id": new_id("prov"),
            "entity_id": entity_id,
            "provenance_class": "vision_estimated",
            "source_photo_id": memory["photograph"]["id"],
            "source_mask_id": entity_id,
            "depth_region_id": None,
            "model": {"id": "sam-3.1", "provider": "meta", "task": "segmentation"},
            "evidence": {
                "original_image_available": True,
                "mask_available": True,
                "depth_estimate_available": False,
                "generated_pixels": False,
                "human_claim": False,
            },
            "model_native_confidence": confidence_record,
            "calibration_status": "not_calibrated",
            "created_at": utc_now(),
            "notes": entity["classifier_note"],
        }
        entity["provenance_ids"] = [observed["id"], estimated["id"]]
        memory["entities"].append(entity)
        memory["provenances"].extend([observed, estimated])
        write_asset(memory["id"], f"masks/{entity_id}.png", (mask.astype(np.uint8) * 255))

    write_asset(memory["id"], "entity_ids.png", entity_map.astype(np.uint8))
    memory["segmentation"]["model_id"] = "sam-3.1"
    memory["segmentation"]["provider"] = "meta"
    memory["segmentation"]["live_meta"] = True
    memory["segmentation"]["note"] = (
        "At least one region uses a SAM 3.1 mask from a live API call. "
        "Regions without that model id are still from the local segmenter."
    )
    memory["invocations"].append(invocation)
    update_memory(memory)
    return memory


def decode_mask_png(mask_png_base64: str) -> bytes:
    return base64.b64decode(mask_png_base64)
