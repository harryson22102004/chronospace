"""Relative depth.

Primary estimator: Depth Anything V2 Small, quantized ONNX
(`onnx-community/depth-anything-v2-small`, file `model_q4.onnx`).

On a synthetic interior probe in this repo, larger output values landed on the
foreground chair and the bottom of the frame, and smaller values landed on the
distant window. The mesh therefore treats larger values as closer. The scale is
relative and uncalibrated. It is not metric distance.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import cv2
import numpy as np

from .config import MODEL_PATH

MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)


@dataclass
class DepthResult:
    disparity: np.ndarray  # float32, HxW, larger = closer
    normalized: np.ndarray  # float32 0..1, 1 = closest
    model_id: str
    provider: str
    duration_ms: float
    note: str


_SESSION = None


def _session():
    global _SESSION
    if _SESSION is not None:
        return _SESSION
    if not MODEL_PATH.exists():
        return None
    import onnxruntime as ort

    _SESSION = ort.InferenceSession(
        str(MODEL_PATH), providers=["CPUExecutionProvider"]
    )
    return _SESSION


def _normalize(disparity: np.ndarray) -> np.ndarray:
    lo = float(np.percentile(disparity, 1))
    hi = float(np.percentile(disparity, 99))
    if hi - lo < 1e-6:
        return np.zeros_like(disparity, dtype=np.float32)
    out = (disparity.astype(np.float32) - lo) / (hi - lo)
    return np.clip(out, 0, 1)


def estimate_depth_anything(rgb: np.ndarray) -> DepthResult | None:
    session = _session()
    if session is None:
        return None
    h, w = rgb.shape[:2]
    side = 518
    resized = cv2.resize(rgb, (side, side), interpolation=cv2.INTER_CUBIC)
    x = resized.astype(np.float32) / 255.0
    x = (x - MEAN) / STD
    tensor = np.transpose(x, (2, 0, 1))[None].astype(np.float32)
    started = time.perf_counter()
    pred = session.run(None, {"pixel_values": tensor})[0][0]
    duration_ms = (time.perf_counter() - started) * 1000
    disp = cv2.resize(pred.astype(np.float32), (w, h), interpolation=cv2.INTER_CUBIC)
    disp = cv2.bilateralFilter(disp, d=5, sigmaColor=0.2, sigmaSpace=5)
    return DepthResult(
        disparity=disp,
        normalized=_normalize(disp),
        model_id="depth-anything-v2-small-q4",
        provider="local-onnx",
        duration_ms=duration_ms,
        note=(
            "Relative depth from Depth Anything V2 Small, quantized ONNX. "
            "Larger values are treated as closer, based on a synthetic probe in "
            "this repository. The values are not meters and are not calibrated."
        ),
    )


def estimate_ground_prior(rgb: np.ndarray) -> DepthResult:
    """Baseline: bottom of the frame is closer. No learned weights."""
    h, w = rgb.shape[:2]
    ys = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    disp = np.repeat(ys, w, axis=1)
    started = time.perf_counter()
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
    disp = disp * 0.85 + (1.0 - gray) * 0.15
    duration_ms = (time.perf_counter() - started) * 1000
    return DepthResult(
        disparity=disp,
        normalized=_normalize(disp),
        model_id="classical-ground-prior-v1",
        provider="local",
        duration_ms=duration_ms,
        note=(
            "Classical baseline. Vertical position is treated as a ground-plane "
            "cue and darker pixels are nudged slightly closer. This is not a "
            "learned depth model."
        ),
    )


def estimate_depth(rgb: np.ndarray) -> DepthResult:
    learned = estimate_depth_anything(rgb)
    if learned is not None:
        return learned
    return estimate_ground_prior(rgb)


def surface_normals(normalized: np.ndarray) -> np.ndarray:
    """Screen-space normals from relative depth. Approximation, not surveyed geometry."""
    gx = cv2.Sobel(normalized, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(normalized, cv2.CV_32F, 0, 1, ksize=3)
    nx = -gx
    ny = -gy
    nz = np.ones_like(normalized) * 0.35
    n = np.stack([nx, ny, nz], axis=-1)
    length = np.linalg.norm(n, axis=-1, keepdims=True) + 1e-6
    unit = n / length
    rgb = ((unit * 0.5 + 0.5) * 255).clip(0, 255).astype(np.uint8)
    return rgb
