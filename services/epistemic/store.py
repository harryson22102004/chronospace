"""JSON memory store on disk."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import numpy as np
from PIL import Image

from .config import GRAPH_PATH, MEMORIES_DIR

_LOCK = threading.Lock()


def _write_image(path: Path, array: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if array.ndim == 3 and array.shape[2] == 3 and path.suffix == ".jpg":
        Image.fromarray(array, mode="RGB").save(path, format="JPEG", quality=92)
        return
    if array.ndim == 3 and array.shape[2] == 4:
        Image.fromarray(array, mode="RGBA").save(path, format="PNG")
        return
    if array.ndim == 2:
        Image.fromarray(array).save(path, format="PNG")
        return
    Image.fromarray(array).save(path)


def save_memory(memory: dict, images: dict[str, np.ndarray]) -> dict:
    folder = MEMORIES_DIR / memory["id"]
    folder.mkdir(parents=True, exist_ok=True)
    for name, array in images.items():
        _write_image(folder / name, array)
    (folder / "memory.json").write_text(json.dumps(memory, indent=2))
    _touch_graph(memory["id"])
    return memory


def update_memory(memory: dict) -> dict:
    folder = MEMORIES_DIR / memory["id"]
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "memory.json").write_text(json.dumps(memory, indent=2))
    return memory


def load_memory(memory_id: str) -> dict:
    path = MEMORIES_DIR / memory_id / "memory.json"
    if not path.exists():
        raise FileNotFoundError(memory_id)
    return json.loads(path.read_text())


def list_memories() -> list[dict]:
    if not MEMORIES_DIR.exists():
        return []
    items = []
    for folder in sorted(MEMORIES_DIR.iterdir()):
        path = folder / "memory.json"
        if path.exists():
            memory = json.loads(path.read_text())
            items.append(_summary(memory))
    items.sort(key=lambda item: item["created_at"], reverse=True)
    return items


def _summary(memory: dict) -> dict:
    return {
        "id": memory["id"],
        "title": memory["title"],
        "created_at": memory["created_at"],
        "sample": memory.get("sample", False),
        "sample_note": memory.get("sample_note"),
        "photo_url": memory["photograph"]["url"],
        "width": memory["photograph"]["width"],
        "height": memory["photograph"]["height"],
        "capture_time": memory["photograph"].get("capture_time"),
        "capture_time_reliability": memory["photograph"].get("capture_time_reliability"),
        "entity_count": len(memory.get("entities", [])),
        "labels": [e["label"] for e in memory.get("entities", []) if e["label"] not in {"wall", "floor", "region"}],
        "live_meta": any(inv.get("live") and inv.get("status") == "succeeded" for inv in memory.get("invocations", [])),
    }


def load_rgb(memory_id: str) -> np.ndarray:
    path = MEMORIES_DIR / memory_id / "photo.jpg"
    image = Image.open(path).convert("RGB")
    return np.asarray(image)


def load_mask(memory: dict, key: str) -> np.ndarray:
    rel = memory["assets"][key]
    path = MEMORIES_DIR.parent / rel if rel.startswith("memories/") else MEMORIES_DIR / memory["id"] / rel
    # assets are stored as memories/{id}/file
    path = MEMORIES_DIR.parents[0] / rel if False else _asset_path(rel)
    image = Image.open(path)
    return np.asarray(image)


def _asset_path(rel: str) -> Path:
    from .config import DATA_DIR

    return DATA_DIR / rel


def write_asset(memory_id: str, name: str, array: np.ndarray) -> None:
    _write_image(MEMORIES_DIR / memory_id / name, array)


def _touch_graph(memory_id: str) -> None:
    with _LOCK:
        graph = load_graph()
        if memory_id not in graph["memory_ids"]:
            graph["memory_ids"].append(memory_id)
            save_graph(graph)


def load_graph() -> dict:
    if not GRAPH_PATH.exists():
        return {"memory_ids": [], "links": []}
    return json.loads(GRAPH_PATH.read_text())


def save_graph(graph: dict) -> None:
    GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
    GRAPH_PATH.write_text(json.dumps(graph, indent=2))


def file_path(rel: str) -> Path:
    from .config import DATA_DIR

    candidate = (DATA_DIR / rel).resolve()
    root = DATA_DIR.resolve()
    if root not in candidate.parents and candidate != root:
        raise ValueError("Path escapes the data directory.")
    return candidate
