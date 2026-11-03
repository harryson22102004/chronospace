from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("CHRONOSPACE_DATA", ROOT / "data"))
_configured_model_path = Path(
    os.environ.get("DEPTH_MODEL_PATH", "models/depth_anything_v2_small_q4.onnx")
)
MODEL_PATH = _configured_model_path if _configured_model_path.is_absolute() else ROOT / _configured_model_path
MEMORIES_DIR = DATA_DIR / "memories"
GRAPH_PATH = DATA_DIR / "graph.json"
MAX_UPLOAD_BYTES = 12_000_000
MAX_EDGE = 1600
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
VISION_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "CHRONOSPACE_ORIGINS",
        "http://127.0.0.1:43123,http://localhost:43123",
    ).split(",")
    if origin.strip()
]
