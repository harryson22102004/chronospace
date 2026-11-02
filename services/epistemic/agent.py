"""Grounded spatial agent.

Tool results are the only source of the narration. A local planner selects
tools when Muse Spark is not called. Muse Spark, when it is called, may choose
the same tools; its free-form prose is stored separately and is not treated as
evidence.
"""

from __future__ import annotations

import re

from .hypotheses import sketch_hypothesis
from .pipeline import new_id, utc_now
from .store import load_rgb, update_memory, write_asset

TOOL_NAMES = [
    "list_scene_entities",
    "get_entity_details",
    "get_entity_provenance",
    "get_scene_relationships",
    "focus_camera_on_entity",
    "highlight_object",
    "change_truth_lens_mode",
    "retrieve_user_memory",
    "add_memory_annotation",
    "create_alternative_hypothesis",
    "get_timeline_events",
]


def tool_schema() -> list[dict]:
    """OpenAI-style function tools for the Responses API."""
    specs = {
        "list_scene_entities": {"type": "object", "properties": {}, "additionalProperties": False},
        "get_entity_details": {
            "type": "object",
            "properties": {"entity_id": {"type": "string"}},
            "required": ["entity_id"],
            "additionalProperties": False,
        },
        "get_entity_provenance": {
            "type": "object",
            "properties": {"entity_id": {"type": "string"}},
            "required": ["entity_id"],
            "additionalProperties": False,
        },
        "get_scene_relationships": {"type": "object", "properties": {}, "additionalProperties": False},
        "focus_camera_on_entity": {
            "type": "object",
            "properties": {"entity_id": {"type": "string"}},
            "required": ["entity_id"],
            "additionalProperties": False,
        },
        "highlight_object": {
            "type": "object",
            "properties": {"entity_id": {"type": "string"}},
            "required": ["entity_id"],
            "additionalProperties": False,
        },
        "change_truth_lens_mode": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["original", "observed", "inferred", "generated", "testimony", "all"],
                }
            },
            "required": ["mode"],
            "additionalProperties": False,
        },
        "retrieve_user_memory": {"type": "object", "properties": {}, "additionalProperties": False},
        "add_memory_annotation": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "speaker": {"type": "string"},
            },
            "required": ["text"],
            "additionalProperties": False,
        },
        "create_alternative_hypothesis": {
            "type": "object",
            "properties": {"claim": {"type": "string"}, "speaker": {"type": "string"}},
            "required": ["claim"],
            "additionalProperties": False,
        },
        "get_timeline_events": {"type": "object", "properties": {}, "additionalProperties": False},
    }
    tools = []
    for name, parameters in specs.items():
        tools.append(
            {
                "type": "function",
                "name": name,
                "description": f"ChronoSpace scene tool `{name}`. Use only information returned by tools.",
                "parameters": parameters,
            }
        )
    return tools


def _entity(memory: dict, entity_id: str) -> dict | None:
    return next((item for item in memory["entities"] if item["id"] == entity_id), None)


def _match_entity(memory: dict, text: str) -> dict | None:
    lowered = text.lower()
    named = [
        entity
        for entity in memory["entities"]
        if entity["label"] not in {"region", "wall", "floor"}
    ]
    # Prefer the longest label that appears in the text.
    named.sort(key=lambda entity: len(entity["label"]), reverse=True)
    for entity in named:
        if entity["label"] in lowered:
            return entity
    aliases = {
        "record": "record player",
        "turntable": "record player",
        "gramophone": "record player",
        "cabinet": "cupboard",
        "closet": "cupboard",
        "couch": "sofa",
        "settee": "sofa",
    }
    for alias, label in aliases.items():
        if re.search(rf"\b{alias}\b", lowered):
            found = next((entity for entity in named if entity["label"] == label), None)
            if found:
                return found
    return None


def execute_tool(memory: dict, name: str, args: dict) -> tuple[dict, dict, list[dict]]:
    """Return result, possibly mutated memory, and viewer actions."""
    actions: list[dict] = []
    if name not in TOOL_NAMES:
        return {"error": "unknown_tool", "name": name}, memory, actions
    if name == "list_scene_entities":
        return {
            "entities": [
                {
                    "id": entity["id"],
                    "label": entity["label"],
                    "content_status": entity["content_status"],
                    "label_origin": entity["label_origin"],
                }
                for entity in memory["entities"]
            ]
        }, memory, actions
    if name in {"get_entity_details", "focus_camera_on_entity", "highlight_object", "get_entity_provenance"}:
        entity = _entity(memory, str(args.get("entity_id", "")))
        if entity is None:
            return {"error": "entity_not_found"}, memory, actions
        if name == "get_entity_details":
            return {
                "id": entity["id"],
                "label": entity["label"],
                "label_origin": entity["label_origin"],
                "content_status": entity["content_status"],
                "classifier_note": entity["classifier_note"],
                "centroid_uv": entity["centroid_uv"],
                "median_normalized_depth": entity["median_normalized_depth"],
                "median_disparity": entity["median_disparity"],
                "depth_model": memory["depth"]["model_id"],
                "depth_note": memory["depth"]["note"],
                "calibration_status": memory["depth"]["calibration_status"],
                "area_fraction": entity["area_fraction"],
            }, memory, actions
        if name == "get_entity_provenance":
            records = [
                prov
                for prov in memory["provenances"]
                if prov.get("entity_id") == entity["id"]
            ]
            return {"entity_id": entity["id"], "records": records}, memory, actions
        action_type = "focus_camera" if name == "focus_camera_on_entity" else "highlight"
        actions.append(
            {
                "type": action_type,
                "entity_id": entity["id"],
                "label": entity["label"],
                "uv": entity["centroid_uv"],
            }
        )
        return {"ok": True, "entity_id": entity["id"], "label": entity["label"], "uv": entity["centroid_uv"]}, memory, actions
    if name == "get_scene_relationships":
        return {"relationships": memory["relationships"]}, memory, actions
    if name == "change_truth_lens_mode":
        mode = args.get("mode")
        allowed = {"original", "observed", "inferred", "generated", "testimony", "all"}
        if mode not in allowed:
            return {"error": "invalid_mode"}, memory, actions
        actions.append({"type": "truth_lens", "mode": mode})
        return {"ok": True, "mode": mode}, memory, actions
    if name == "retrieve_user_memory":
        return {"testimonies": memory["testimonies"], "hypotheses": _public_hypotheses(memory)}, memory, actions
    if name == "add_memory_annotation":
        text = str(args.get("text", "")).strip()
        if not text:
            return {"error": "empty_testimony"}, memory, actions
        testimony, memory = _add_testimony(memory, text, args.get("speaker"))
        actions.append({"type": "show_testimony", "testimony_id": testimony["id"]})
        actions.append({"type": "truth_lens", "mode": "testimony"})
        return {"testimony": testimony}, memory, actions
    if name == "create_alternative_hypothesis":
        claim = str(args.get("claim", "")).strip()
        if not claim:
            return {"error": "empty_claim"}, memory, actions
        rgb = load_rgb(memory["id"])
        built = sketch_hypothesis(memory, rgb, claim, args.get("speaker"))
        if not built.get("created"):
            return built, memory, actions
        write_asset(memory["id"], f"hypotheses/{built['record']['id']}.png", built["rgba"])
        memory["hypotheses"].append(built["record"])
        memory["provenances"].append(built["provenance"])
        memory["active_hypothesis_id"] = built["record"]["id"]
        memory["assets"]["hypothesis"] = built["record"]["artifact_url"]
        generated = (built["rgba"][..., 3] > 0).astype("uint8") * 255
        write_asset(memory["id"], "generated.png", generated)
        update_memory(memory)
        actions.append({"type": "show_hypothesis", "hypothesis_id": built["record"]["id"]})
        actions.append({"type": "truth_lens", "mode": "generated"})
        return {"hypothesis": _public_hypothesis(built["record"])}, memory, actions
    if name == "get_timeline_events":
        return {"events": timeline_for(memory)}, memory, actions
    return {"error": "unhandled"}, memory, actions


def _public_hypothesis(record: dict) -> dict:
    return {key: value for key, value in record.items()}


def _public_hypotheses(memory: dict) -> list[dict]:
    return [_public_hypothesis(item) for item in memory["hypotheses"]]


def _add_testimony(memory: dict, text: str, speaker: str | None) -> tuple[dict, dict]:
    check = assess_claim(memory, text)
    testimony = {
        "id": new_id("tes"),
        "text": text,
        "speaker": speaker,
        "source": "typed",
        "transcript_model": None,
        "confirmed": True,
        "created_at": utc_now(),
        "related_entity_ids": check["related_entity_ids"],
        "verification": check["verification"],
        "verification_note": check["note"],
    }
    memory["testimonies"].append(testimony)
    provenance = {
        "id": new_id("prov"),
        "entity_id": check["related_entity_ids"][0] if check["related_entity_ids"] else None,
        "testimony_id": testimony["id"],
        "provenance_class": "human_testimony",
        "source_photo_id": memory["photograph"]["id"],
        "source_mask_id": None,
        "depth_region_id": None,
        "model": None,
        "evidence": {
            "original_image_available": True,
            "mask_available": False,
            "depth_estimate_available": False,
            "generated_pixels": False,
            "human_claim": True,
        },
        "model_native_confidence": None,
        "calibration_status": "not_applicable",
        "created_at": testimony["created_at"],
        "notes": "Human testimony. It is not converted into photographic evidence.",
    }
    testimony["provenance_id"] = provenance["id"]
    memory["provenances"].append(provenance)
    _paint_testimony_mask(memory, check["related_entity_ids"])
    update_memory(memory)
    return testimony, memory


def _paint_testimony_mask(memory: dict, entity_ids: list[str]) -> None:
    import numpy as np
    from PIL import Image
    from .store import _asset_path

    path = _asset_path(memory["assets"]["entity_ids"])
    ids = np.asarray(Image.open(path))
    if ids.ndim == 3:
        ids = ids[..., 0]
    mask = np.zeros(ids.shape, np.uint8)
    index_by_id = {entity["id"]: entity["index"] for entity in memory["entities"]}
    for entity_id in entity_ids:
        value = index_by_id.get(entity_id)
        if value is not None:
            mask[ids == value] = 255
    if mask.any():
        write_asset(memory["id"], "testimony.png", mask)


def assess_claim(memory: dict, text: str) -> dict:
    entity = _match_entity(memory, text)
    mentioned_missing = _missing_object(text, memory)
    if mentioned_missing:
        return {
            "verification": "unresolved",
            "note": (
                f"The claim mentions {mentioned_missing}, and no segmented region has that label. "
                "The photograph neither shows it nor proves it was absent."
            ),
            "related_entity_ids": [],
        }
    if entity is None:
        return {
            "verification": "unresolved",
            "note": "The claim does not name a region this reconstruction contains, so it stays unresolved.",
            "related_entity_ids": [],
        }
    if "next to" in text.lower() or "beside" in text.lower() or "near" in text.lower():
        other = _second_entity(memory, text, entity)
        if other is None:
            return {
                "verification": "unresolved",
                "note": f"The scene contains {entity['label']}, but the other place in the claim is not a known region.",
                "related_entity_ids": [entity["id"]],
            }
        near = any(
            rel["type"] == "located_near"
            and {rel["source_id"], rel["target_id"]} == {entity["id"], other["id"]}
            for rel in memory["relationships"]
        )
        if near:
            return {
                "verification": "supported",
                "note": (
                    f"{entity['label']} and {other['label']} have centroids the layout rule treats as nearby. "
                    "That is image-plane proximity, not a surveyed measurement, and it does not prove a memory."
                ),
                "related_entity_ids": [entity["id"], other["id"]],
            }
        return {
            "verification": "contradicted",
            "note": (
                f"Both {entity['label']} and {other['label']} are in the segmentation, and their centroids "
                "are not marked located_near. This contradicts the spatial part of the claim. It does not rewrite the photograph."
            ),
            "related_entity_ids": [entity["id"], other["id"]],
        }
    if entity["content_status"] == "unknown":
        return {
            "verification": "unresolved",
            "note": "The region is visible only as a dark area. Its contents are unresolved.",
            "related_entity_ids": [entity["id"]],
        }
    return {
        "verification": "supported",
        "note": f"A region labeled {entity['label']} is in the segmentation. The label itself is a heuristic unless SAM replaced it.",
        "related_entity_ids": [entity["id"]],
    }


def _missing_object(text: str, memory: dict) -> str | None:
    vocabulary = ["piano", "bookshelf", "bookcase", "dog", "cat", "bicycle", "television", "tree"]
    labels = {entity["label"] for entity in memory["entities"]}
    for word in vocabulary:
        if word in text.lower() and word not in labels and not any(word in label for label in labels):
            return word
    return None


def _second_entity(memory: dict, text: str, first: dict) -> dict | None:
    lowered = text.lower()
    for entity in memory["entities"]:
        if entity["id"] == first["id"]:
            continue
        if entity["label"] in {"wall", "floor", "region"}:
            continue
        if entity["label"] in lowered:
            return entity
    return None


def timeline_for(memory: dict) -> list[dict]:
    events = []
    capture = memory["photograph"].get("capture_time")
    reliability = memory["photograph"].get("capture_time_reliability")
    if capture and reliability in {"exif", "user_asserted"}:
        events.append(
            {
                "id": new_id("time"),
                "kind": "capture_time",
                "at": capture,
                "reliability": reliability,
                "memory_id": memory["id"],
                "note": "A capture time is present only because EXIF was authorized or a person asserted it.",
            }
        )
    return events


def local_turn(memory: dict, message: str) -> dict:
    text = message.strip()
    lowered = text.lower()
    trace = []
    actions: list[dict] = []

    def run(name: str, args: dict) -> dict:
        nonlocal memory
        result, memory, extra = execute_tool(memory, name, args)
        trace.append({"name": name, "args": args, "result": _shrink(result)})
        actions.extend(extra)
        return result

    testimony_like = any(
        token in lowered
        for token in ["remember", "recalls", "recall", "grandmother", "grandfather", "used to", "i think there"]
    )
    asks_hidden = any(token in lowered for token in ["behind", "inside the", "hidden", "what was in the corner", "unobserved"])
    asks_metric = any(token in lowered for token in ["how many meters", "exact distance", "in meters", "how far in"])
    asks_people = "how many people" in lowered or "who was there" in lowered
    asks_timeline = "timeline" in lowered or "when was" in lowered or "what year" in lowered

    if testimony_like:
        speaker = None
        match = re.search(r"\b(grandmother|grandfather|mother|father|uncle|aunt)\b", lowered)
        if match:
            speaker = match.group(1)
        result = run("add_memory_annotation", {"text": text, "speaker": speaker})
        narration = (
            "I stored that as human testimony, separate from the photograph. "
            + result.get("testimony", {}).get("verification_note", "")
        )
        if result.get("testimony", {}).get("verification") == "unresolved":
            narration += " I can sketch an alternative in the unobserved region if you want one. It would be a hypothesis, not a recovered fact."
            if any(entity["content_status"] == "unknown" for entity in memory["entities"]):
                actions.append({"type": "offer_hypothesis", "claim": text, "speaker": speaker})
        return _pack(memory, narration, trace, actions)

    if asks_metric or asks_people:
        run("list_scene_entities", {})
        narration = (
            "I can't answer that from this photograph. Relative depth is uncalibrated, so there is no distance in meters, "
            "and the image does not say who was present or how many people there were."
        )
        return _pack(memory, narration, trace, actions)

    if asks_timeline:
        events = run("get_timeline_events", {})
        if not events.get("events"):
            narration = (
                "There is no verified capture time on this photograph. "
                "I will not invent a historical date or a sequence from a single image."
            )
        else:
            narration = "The only time attached to this photograph is the one stored with its reliability flag: " + "; ".join(
                f"{event['at']} ({event['reliability']})" for event in events["events"]
            )
        return _pack(memory, narration, trace, actions)

    if asks_hidden:
        target = _match_entity(memory, text) or next(
            (entity for entity in memory["entities"] if entity["content_status"] == "unknown"),
            None,
        )
        if target is None:
            run("list_scene_entities", {})
            narration = "Nothing in the segmentation is marked as a hidden or unobserved region, so I will not describe what might be there."
            return _pack(memory, narration, trace, actions)
        run("get_entity_details", {"entity_id": target["id"]})
        run("change_truth_lens_mode", {"mode": "observed"})
        run("highlight_object", {"entity_id": target["id"]})
        if target["content_status"] == "unknown" or "behind" in lowered:
            unknown = next((e for e in memory["entities"] if e["content_status"] == "unknown"), None)
            narration = (
                f"The region labeled {target['label']} is estimated by {target['label_origin']}. "
            )
            if unknown is not None:
                narration += (
                    f"A separate region labeled {unknown['label']} is dark in the photograph. "
                    "Those pixels were recorded, and what occupies that space is unknown. I will not invent an object there."
                )
            else:
                narration += "I do not have observed pixels for anything behind it, so that space stays unknown."
        else:
            narration = f"I can show {target['label']}. I don't have a measurement of the space behind it."
        return _pack(memory, narration, trace, actions)

    wants_focus = any(token in lowered for token in ["show", "take me", "where", "focus", "look at", "go to", "find"])
    entity = _match_entity(memory, text)
    if entity is not None and wants_focus:
        run("focus_camera_on_entity", {"entity_id": entity["id"]})
        run("highlight_object", {"entity_id": entity["id"]})
        details = run("get_entity_details", {"entity_id": entity["id"]})
        run("get_entity_provenance", {"entity_id": entity["id"]})
        narration = (
            f"The reconstruction contains a region labeled {entity['label']}. "
            f"The label comes from {entity['label_origin']}. "
            f"Its appearance is the original photograph inside the mask. "
            f"Relative depth at the region median is {details['median_disparity']} on the {details['depth_model']} scale, "
            f"where higher means closer in this project's probe. That scale is {details['calibration_status'].replace('_', ' ')}. "
            "I am moving the camera toward it."
        )
        return _pack(memory, narration, trace, actions)
    if entity is not None:
        details = run("get_entity_details", {"entity_id": entity["id"]})
        run("highlight_object", {"entity_id": entity["id"]})
        narration = (
            f"{entity['label']} is a {entity['content_status'].replace('_', ' ')} region. "
            f"{entity['classifier_note']} "
            f"Median relative depth is {details['median_disparity']} ({details['calibration_status'].replace('_', ' ')})."
        )
        return _pack(memory, narration, trace, actions)

    run("list_scene_entities", {})
    narration = (
        "I don't have an entity, a testimony, or a measurement that answers that. "
        "I can list the regions the segmenter found, and I won't fill the gap with a guess."
    )
    return _pack(memory, narration, trace, actions)


def _shrink(result: dict) -> dict:
    if "records" in result:
        return {"provenance_count": len(result["records"]), "entity_id": result.get("entity_id")}
    if "entities" in result:
        return {"entities": [e["label"] for e in result["entities"]]}
    if "relationships" in result:
        return {"count": len(result["relationships"])}
    return result


def summarize_trace(trace: list[dict]) -> str:
    """Narration built only from tool results. Used after Muse Spark selects tools."""
    sentences = []
    for step in trace:
        result = step.get("result") or {}
        name = step["name"]
        if result.get("error") == "entity_not_found":
            sentences.append("That object is not in the scene graph.")
        elif name == "focus_camera_on_entity" and result.get("label"):
            sentences.append(f"I am moving the camera to the region labeled {result['label']}.")
        elif name == "get_entity_details" and result.get("label"):
            sentences.append(
                f"{result['label']} is marked {str(result.get('content_status', '')).replace('_', ' ')}. "
                f"{result.get('classifier_note', '')} "
                f"Median relative depth is {result.get('median_disparity')} on {result.get('depth_model')}, "
                f"which is {str(result.get('calibration_status', 'not_calibrated')).replace('_', ' ')}."
            )
        elif name == "add_memory_annotation" and result.get("testimony"):
            testimony = result["testimony"]
            sentences.append(
                "Stored as human testimony, not as photographic evidence. " + testimony.get("verification_note", "")
            )
        elif name == "create_alternative_hypothesis" and result.get("hypothesis"):
            hypothesis = result["hypothesis"]
            sentences.append(
                f"Created {hypothesis['title']} with {hypothesis['generator']['model_id']}. "
                "It is hypothetical and does not replace the photograph."
            )
        elif name == "create_alternative_hypothesis" and result.get("reason"):
            sentences.append(result["reason"])
        elif name == "get_timeline_events":
            events = result.get("events") or []
            if not events:
                sentences.append("No verified capture time is stored, so there is no historical sequence to show.")
            else:
                sentences.append("Capture times on file: " + "; ".join(f"{e['at']} ({e['reliability']})" for e in events))
        elif name == "list_scene_entities":
            raw = result.get("entities") or []
            if raw and isinstance(raw[0], dict):
                labels = [item["label"] for item in raw]
            else:
                labels = raw
            if labels:
                sentences.append("Regions in the scene graph: " + ", ".join(labels) + ".")
    if not sentences:
        sentences.append("The tools did not return a fact I can state.")
    return " ".join(sentences)


def _pack(memory: dict, narration: str, trace: list[dict], actions: list[dict]) -> dict:
    return {
        "narration": narration,
        "tool_trace": trace,
        "actions": actions,
        "commentary": None,
        "source": {
            "model_id": "local-evidence-orchestrator",
            "provider": "local",
            "live": False,
        },
        "memory_id": memory["id"],
    }
