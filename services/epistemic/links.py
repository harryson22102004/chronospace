"""Cross-photograph identity proposals.

A shared label plus a color-histogram correlation is a proposal, not an identity.
"""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

from .pipeline import new_id, utc_now
from .store import _asset_path, list_memories, load_memory, load_rgb, save_graph, load_graph


def _hist(rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    pixels = hsv[mask]
    if len(pixels) < 20:
        return np.zeros((16 * 8,), np.float32)
    hist, _, _ = np.histogram2d(
        pixels[:, 0], pixels[:, 1], bins=(16, 8), range=[[0, 180], [0, 256]]
    )
    flat = hist.astype(np.float32).ravel()
    flat /= np.linalg.norm(flat) + 1e-6
    return flat


def _mask(entity: dict) -> np.ndarray:
    image = np.asarray(Image.open(_asset_path(entity["mask_url"])).convert("L"))
    return image > 127


def propose_for(memory: dict) -> list[dict]:
    graph = load_graph()
    created = []
    existing = {
        tuple(sorted((link["a"]["entity_id"], link["b"]["entity_id"])))
        for link in graph["links"]
    }
    rgb = load_rgb(memory["id"])
    for summary in list_memories():
        if summary["id"] == memory["id"]:
            continue
        other = load_memory(summary["id"])
        other_rgb = load_rgb(other["id"])
        for entity in memory["entities"]:
            if entity["label"] in {"wall", "floor", "region"}:
                continue
            for twin in other["entities"]:
                if twin["label"] != entity["label"]:
                    continue
                key = tuple(sorted((entity["id"], twin["id"])))
                if key in existing:
                    continue
                correlation = float(np.dot(_hist(rgb, _mask(entity)), _hist(other_rgb, _mask(twin))))
                if correlation < 0.75:
                    continue
                link = {
                    "id": new_id("link"),
                    "type": "same_possible_entity",
                    "status": "proposed",
                    "created_at": utc_now(),
                    "a": {"memory_id": memory["id"], "entity_id": entity["id"], "label": entity["label"]},
                    "b": {"memory_id": other["id"], "entity_id": twin["id"], "label": twin["label"]},
                    "cues": [
                        f"shared_label:{entity['label']}",
                        f"hsv_histogram_correlation:{correlation:.3f}",
                    ],
                    "note": (
                        "The label matches and the color histograms are similar. "
                        "This is a proposal. The photographs have not been geometrically verified, "
                        "and the entities are not claimed to be the same object."
                    ),
                }
                graph["links"].append(link)
                created.append(link)
                existing.add(key)
    save_graph(graph)
    memory["links"] = [
        link
        for link in graph["links"]
        if memory["id"] in {link["a"]["memory_id"], link["b"]["memory_id"]}
    ]
    return created


def set_link_status(link_id: str, status: str) -> dict:
    if status not in {"proposed", "confirmed", "rejected"}:
        raise ValueError("Status must be proposed, confirmed, or rejected.")
    graph = load_graph()
    for link in graph["links"]:
        if link["id"] == link_id:
            link["status"] = status
            save_graph(graph)
            return link
    raise FileNotFoundError(link_id)
