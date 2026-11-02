"""Painted reference photographs.

These are drawings made by this repository so the demo has a known scene
without using someone else's photograph. They are not historical records and
they carry no camera timestamp.
"""

from __future__ import annotations

import cv2
import numpy as np


def _room(width: int = 960, height: int = 640, close: bool = False) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    img = np.zeros((height, width, 3), np.uint8)
    truth: dict[str, np.ndarray] = {}
    for y in range(height):
        t = y / height
        wall = np.array([214, 196, 170]) * (0.72 + 0.28 * t) + np.array([18, 10, 4]) * (1 - t)
        img[y, :] = wall.clip(0, 255).astype(np.uint8)
    floor_y = int(height * 0.72)
    for y in range(floor_y, height):
        t = (y - floor_y) / max(1, height - floor_y)
        img[y, :] = (np.array([128, 96, 68]) * (0.75 + 0.25 * t)).astype(np.uint8)

    def stamp(name: str, painter) -> None:
        mask = np.zeros((height, width), np.uint8)
        painter(mask)
        truth[name] = mask.astype(bool)

    def window(mask: np.ndarray) -> None:
        if close:
            cv2.rectangle(mask, (40, 30), (280, 250), 1, -1)
        else:
            cv2.rectangle(mask, (70, 70), (250, 250), 1, -1)

    def curtain(mask: np.ndarray) -> None:
        if close:
            cv2.rectangle(mask, (300, 20), (360, 270), 1, -1)
        else:
            cv2.rectangle(mask, (262, 58), (318, 268), 1, -1)

    def record(mask: np.ndarray) -> None:
        if close:
            cv2.rectangle(mask, (430, 250), (760, 520), 1, -1)
            cv2.circle(mask, (595, 340), 78, 1, -1)
        else:
            cv2.rectangle(mask, (390, 300), (590, 470), 1, -1)
            cv2.circle(mask, (490, 355), 48, 1, -1)

    def cupboard(mask: np.ndarray) -> None:
        if close:
            return
        cv2.rectangle(mask, (760, 150), (930, 500), 1, -1)

    def sofa(mask: np.ndarray) -> None:
        if close:
            return
        cv2.rectangle(mask, (300, 470), (700, 610), 1, -1)

    def lamp(mask: np.ndarray) -> None:
        if close:
            return
        cv2.rectangle(mask, (650, 250), (690, 430), 1, -1)
        cv2.rectangle(mask, (630, 210), (710, 260), 1, -1)

    def clock(mask: np.ndarray) -> None:
        if close:
            return
        cv2.circle(mask, (560, 120), 36, 1, -1)

    def corner(mask: np.ndarray) -> None:
        if close:
            return
        cv2.rectangle(mask, (932, 168), (959, 520), 1, -1)

    for name, fn in (
        ("window", window),
        ("curtain", curtain),
        ("record player", record),
        ("cupboard", cupboard),
        ("sofa", sofa),
        ("lamp", lamp),
        ("clock", clock),
        ("unobserved corner", corner),
    ):
        stamp(name, fn)

    # Paint in an order that matches occlusion: wall already down, then objects.
    def fill(name: str, color: tuple[int, int, int]) -> None:
        if name not in truth or not truth[name].any():
            return
        img[truth[name]] = color

    fill("window", (236, 240, 244))
    # mullions
    if truth["window"].any():
        ys, xs = np.where(truth["window"])
        x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
        cv2.line(img, ((x0 + x1) // 2, y0), ((x0 + x1) // 2, y1), (180, 170, 150), 4)
        cv2.line(img, (x0, (y0 + y1) // 2), (x1, (y0 + y1) // 2), (180, 170, 150), 4)
    fill("curtain", (176, 112, 108))
    fill("cupboard", (92, 58, 36))
    cv2.line(img, (845, 160), (845, 490), (70, 44, 28), 3) if not close else None
    fill("sofa", (150, 78, 62))
    fill("record player", (120, 78, 48))
    if truth["record player"].any():
        if close:
            cv2.circle(img, (595, 340), 78, (18, 16, 16), -1)
            cv2.circle(img, (595, 340), 16, (196, 160, 90), -1)
        else:
            cv2.circle(img, (490, 355), 48, (16, 14, 14), -1)
            cv2.circle(img, (490, 355), 10, (210, 170, 96), -1)
    fill("lamp", (232, 214, 180))
    fill("clock", (48, 62, 74))
    if not close:
        cv2.circle(img, (560, 120), 28, (214, 176, 110), 4)
    fill("unobserved corner", (12, 10, 9))
    return img, truth


def living_room() -> tuple[np.ndarray, dict[str, np.ndarray]]:
    return _room(close=False)


def record_detail() -> tuple[np.ndarray, dict[str, np.ndarray]]:
    return _room(close=True)
