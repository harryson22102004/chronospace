from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("CHRONOSPACE_DATA", ROOT / "data"))
MODEL_PATH = Path(
    os.environ.get(
        "DEPTH_MODEL_PATH",
        ROOT / "models" / "depth_anything_v2_small_q4.onnx",
    )
)
MEMORIES_DIR = DATA_DIR / "memories"
GRAPH_PATH = DATA_DIR / "graph.json"
MAX_UPLOAD_BYTES = 12_000_000
MAX_EDGE = 1600
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
