"""Region decomposition.

Classical segmenter: Lab quantization, connected components, one dark Hough
circle, and shape rules. It is not SAM. A label is a heuristic, and the
provenance record says so. When SAM 3.1 actually returns a mask, that mask
replaces the matching region and the model id becomes `sam-3.1`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass
class Region:
    label: str
    label_origin: str
    mask: np.ndarray
    bbox: tuple[int, int, int, int]
    content_status: str
    animation: str | None = None
    classifier_note: str = ""
    extras: dict = field(default_factory=dict)


def iou(a: np.ndarray, b: np.ndarray) -> float:
    inter = np.logical_and(a, b).sum()
    union = np.logical_or(a, b).sum()
    if union == 0:
        return 0.0
    return float(inter / union)


def _percentile_bbox(mask: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return (0, 0, 0, 0)
    x0, x1 = np.percentile(xs, [1, 99])
    y0, y1 = np.percentile(ys, [1, 99])
    return (int(x0), int(y0), max(1, int(x1 - x0) + 1), max(1, int(y1 - y0) + 1))


def _circularity(mask: np.ndarray) -> float:
    area = float(mask.sum())
    if area < 10:
        return 0.0
    contours, _ = cv2.findContours(
        mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    if not contours:
        return 0.0
    per = cv2.arcLength(max(contours, key=cv2.contourArea), True)
    if per <= 1:
        return 0.0
    return float(4 * np.pi * area / (per * per))


def _lab_means(rgb: np.ndarray, mask: np.ndarray) -> tuple[float, float, float]:
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    sample = lab[mask]
    if len(sample) == 0:
        return (0.0, 0.0, 0.0)
    mean = sample.mean(axis=0)
    return float(mean[0]) * 100 / 255, float(mean[1]) - 128, float(mean[2]) - 128


def _quantize(rgb: np.ndarray, k: int = 9) -> np.ndarray:
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    pixels = lab.reshape(-1, 3).astype(np.float32)
    # Subsample for the centers, then assign everyone.
    rng = np.random.default_rng(0)
    take = pixels if len(pixels) < 40_000 else pixels[rng.choice(len(pixels), 40_000, replace=False)]
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 24, 0.8)
    _, _, centers = cv2.kmeans(take, k, None, criteria, 3, cv2.KMEANS_PP_CENTERS)
    centers = centers.astype(np.float32)
    labels = np.empty((pixels.shape[0],), np.int32)
    step = 200_000
    for start in range(0, pixels.shape[0], step):
        chunk = pixels[start : start + step]
        dist = ((chunk[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
        labels[start : start + step] = dist.argmin(axis=1)
    return labels.reshape(rgb.shape[:2])


def _components(labels: np.ndarray, min_area: int) -> list[np.ndarray]:
    masks: list[np.ndarray] = []
    for value in np.unique(labels):
        raw = (labels == value).astype(np.uint8)
        count, cc, stats, _ = cv2.connectedComponentsWithStats(raw, 8)
        for i in range(1, count):
            if stats[i, cv2.CC_STAT_AREA] < min_area:
                continue
            masks.append(cc == i)
    return masks


def _features(rgb: np.ndarray, mask: np.ndarray) -> dict:
    h, w = mask.shape
    x, y, bw, bh = _percentile_bbox(mask)
    L, a, b = _lab_means(rgb, mask)
    return {
        "bbox": (x, y, bw, bh),
        "area_frac": float(mask.sum()) / float(h * w),
        "aspect": bh / max(bw, 1),
        "solidity": float(mask.sum()) / max(bw * bh, 1),
        "circularity": _circularity(mask),
        "L": L,
        "a": a,
        "b": b,
        "chroma": float(np.hypot(a, b)),
        "cy": (y + bh / 2) / h,
        "cx": (x + bw / 2) / w,
        "width_frac": bw / w,
        "near_right": x + bw > w * 0.9,
        "near_bottom": y + bh > h * 0.9,
    }


def _dark_record_player(rgb: np.ndarray) -> Region | None:
    h, w = rgb.shape[:2]
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    blur = cv2.medianBlur(gray, 5)
    circles = cv2.HoughCircles(
        blur,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=h // 6,
        param1=120,
        param2=32,
        minRadius=max(10, w // 70),
        maxRadius=w // 6,
    )
    if circles is None:
        return None
    best = None
    for circle in np.round(circles[0]).astype(int):
        cx, cy, radius = (int(v) for v in circle)
        if cy - radius < 0 or cy + radius >= h or cx - radius < 0 or cx + radius >= w:
            continue
        disc = np.zeros((h, w), np.uint8)
        cv2.circle(disc, (cx, cy), radius, 1, -1)
        disc_b = disc.astype(bool)
        darkness = float(gray[disc_b].mean())
        if darkness > 55:
            continue
        # Prefer a darker, larger disc.
        score = darkness - radius * 0.15
        if best is None or score < best[0]:
            best = (score, cx, cy, radius, disc_b, darkness)
    if best is None:
        return None
    _, cx, cy, radius, disc_b, darkness = best
    cabinet = np.zeros((h, w), np.uint8)
    x0 = max(0, cx - int(radius * 2.1))
    x1 = min(w - 1, cx + int(radius * 2.1))
    y0 = max(0, cy - int(radius * 0.35))
    y1 = min(h - 1, cy + int(radius * 3.2))
    cabinet[y0:y1, x0:x1] = 1
    wood = gray < 150
    mask = np.logical_and(cabinet.astype(bool), wood)
    mask = np.logical_or(mask, disc_b)
    return Region(
        label="record player",
        label_origin="hough-circle-on-cabinet-v1",
        mask=mask,
        bbox=_percentile_bbox(mask),
        content_status="observed",
        classifier_note=(
            f"Hough circle with mean gray {darkness:.0f} (dark disc) expanded onto "
            "the darker rectangle around it. Shape rule, not a trained detector."
        ),
        extras={"circle": [cx, cy, radius], "mean_gray": darkness},
    )


def _label_for(feat: dict, h: int, w: int) -> tuple[str, str, str, str | None]:
    """Return label, note, content_status, animation."""
    if feat["area_frac"] > 0.18 and feat["chroma"] < 22 and feat["L"] > 45 and feat["cy"] < 0.62:
        return (
            "wall",
            "Large low-chroma region behind the other objects. It is the visible background, not a measured plane.",
            "observed",
            None,
        )
    if (
        feat["L"] > 82
        and feat["chroma"] < 14
        and feat["cy"] < 0.5
        and 0.012 < feat["area_frac"] < 0.12
        and feat["solidity"] > 0.55
        and feat["width_frac"] < 0.4
    ):
        return (
            "window",
            "Bright, low-chroma, compact region in the upper frame.",
            "observed",
            None,
        )
    if feat["cy"] < 0.3 and feat["b"] < -8 and feat["area_frac"] > 0.05 and feat["L"] > 45:
        return ("sky", "Upper blue cluster. Anything outside the frame is unknown.", "observed", None)
    if feat["a"] < -10 and feat["area_frac"] > 0.02:
        return (
            "foliage",
            "Green cluster. Leaf motion in the viewer is a shader, not a fluid simulation.",
            "observed",
            "foliage",
        )
    if (
        feat["L"] < 18
        and feat["area_frac"] > 0.006
        and (feat["near_right"] or feat["near_bottom"] or feat["cx"] > 0.72)
        and feat["cy"] > 0.25
    ):
        return (
            "unobserved corner",
            "Very dark region at the edge of the frame. Those pixels were photographed, but the contents are not resolved.",
            "unknown",
            None,
        )
    if (
        feat["aspect"] > 1.15
        and 0.03 < feat["area_frac"] < 0.22
        and 16 < feat["L"] < 55
        and feat["b"] > 6
        and feat["cy"] < 0.8
    ):
        return (
            "cupboard",
            "Tall dark warm region. The cupboard name is a color and aspect rule.",
            "observed",
            None,
        )
    if (
        feat["cy"] > 0.55
        and feat["chroma"] > 16
        and feat["aspect"] < 0.95
        and feat["area_frac"] > 0.035
        and feat["width_frac"] < 0.75
    ):
        return (
            "sofa",
            "Wide saturated region low in the frame. Furniture type is a layout rule.",
            "observed",
            None,
        )
    if feat["cy"] > 0.68 and feat["width_frac"] > 0.55 and feat["chroma"] < 22 and feat["area_frac"] > 0.06:
        return ("floor", "Wide low region spanning most of the frame.", "observed", None)
    if (
        0.002 < feat["area_frac"] < 0.025
        and feat["circularity"] > 0.5
        and feat["cy"] < 0.42
        and 15 < feat["L"] < 75
        and feat["chroma"] < 28
    ):
        return ("clock", "Small round region on the upper wall.", "observed", "clock")
    if (
        feat["aspect"] > 1.7
        and feat["width_frac"] < 0.12
        and 0.006 < feat["area_frac"] < 0.05
        and feat["L"] > 65
    ):
        return ("lamp", "Narrow bright upright region. The lamp name is a shape rule.", "observed", None)
    return ("region", "Connected region from Lab quantization, left unnamed.", "observed", None)


def _adjacent(a: np.ndarray, b: np.ndarray, pad: int = 18) -> bool:
    kernel = np.ones((pad, pad), np.uint8)
    dil = cv2.dilate(a.astype(np.uint8), kernel)
    return bool(np.logical_and(dil.astype(bool), b).any())


def _merge_same(regions: list[Region]) -> list[Region]:
    merged: list[Region] = []
    used = [False] * len(regions)
    for i, region in enumerate(regions):
        if used[i]:
            continue
        mask = region.mask.copy()
        group = [region]
        used[i] = True
        changed = True
        while changed:
            changed = False
            for j, other in enumerate(regions):
                if used[j] or other.label != region.label or region.label == "region":
                    continue
                if _adjacent(mask, other.mask, 28):
                    mask = np.logical_or(mask, other.mask)
                    group.append(other)
                    used[j] = True
                    changed = True
        if len(group) == 1:
            merged.append(region)
            continue
        merged.append(
            Region(
                label=region.label,
                label_origin=region.label_origin,
                mask=mask,
                bbox=_percentile_bbox(mask),
                content_status=region.content_status,
                animation=region.animation,
                classifier_note=region.classifier_note + " Adjacent pieces with the same label were merged.",
            )
        )
    return merged


def segment_image(rgb: np.ndarray) -> list[Region]:
    h, w = rgb.shape[:2]
    filtered = cv2.bilateralFilter(rgb, d=5, sigmaColor=24, sigmaSpace=5)
    labels = _quantize(filtered, k=9)
    min_area = int(0.0022 * h * w)
    parts = _components(labels, min_area)
    record = _dark_record_player(filtered)
    claimed = record.mask.copy() if record else np.zeros((h, w), dtype=bool)
    regions: list[Region] = []
    if record is not None:
        regions.append(record)

    for mask in parts:
        remain = np.logical_and(mask, np.logical_not(claimed))
        if remain.sum() < min_area:
            continue
        feat = _features(rgb, remain)
        label, note, content, animation = _label_for(feat, h, w)
        # Curtains are tall, moderately saturated, and touch a window.
        regions.append(
            Region(
                label=label,
                label_origin="chromatic-heuristic-v1",
                mask=remain,
                bbox=feat["bbox"],
                content_status=content,
                animation=animation,
                classifier_note=note,
            )
        )
        claimed |= remain

    # Curtain pass: tall regions touching a window, before the generic merge.
    windows = [r for r in regions if r.label == "window"]
    if windows:
        window_union = np.any(np.stack([r.mask for r in windows]), axis=0)
        relabeled: list[Region] = []
        for region in regions:
            feat = _features(rgb, region.mask)
            if (
                region.label == "region"
                and feat["aspect"] > 1.45
                and 0.006 < feat["area_frac"] < 0.08
                and feat["chroma"] > 12
                and _adjacent(window_union, region.mask, 24)
            ):
                relabeled.append(
                    Region(
                        label="curtain",
                        label_origin="chromatic-heuristic-v1",
                        mask=region.mask,
                        bbox=region.bbox,
                        content_status="observed",
                        animation="curtain",
                        classifier_note="Tall saturated region beside a bright window. Viewer motion is a shader.",
                    )
                )
            else:
                relabeled.append(region)
        regions = relabeled

    regions = _merge_same(regions)
    # Drop regions that are almost empty after merges.
    regions = [r for r in regions if r.mask.mean() > 0.003]
    regions.sort(key=lambda r: int(r.mask.sum()), reverse=True)
    return regions
