"""Synthetic blob detector — license-clean test anchor.

Pure numpy. Finds bright-on-dark (or dark-on-bright) blobs via:
1. Otsu thresholding to split foreground / background.
2. Connected-components labelling (4-connectivity).
3. Per-component bounding box + confidence = area / max-area.

This is **not** a pathology detector — it's a deterministic test
target that keeps the detection subpackage honest when
``ultralytics`` isn't installed, and a CI-safe fallback for
every gated detection stub. Real YOLO land in the YOLO adapter.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from openpathai.detection.schema import BoundingBox, DetectionResult

__all__ = ["SyntheticDetector"]


class SyntheticDetector:
    """Pure-numpy blob detector used as the universal detection fallback."""

    id: str = "synthetic_blob"
    display_name: str = "Synthetic blob detector (Otsu + connected components)"
    gated: bool = False
    weight_source: str | None = None
    input_size: tuple[int, int] = (512, 512)
    tier_compatibility: frozenset[str] = frozenset({"T1", "T2", "T3"})
    vram_gb: float = 0.0
    license: str = "MIT"
    citation: str = "OpenPathAI Phase 14 synthetic detector (pure numpy)."

    def __init__(self, class_name: str = "blob") -> None:
        self._class_name = class_name

    def build(self, pretrained: bool = True) -> None:
        return None  # No weights to load.

    def detect(
        self,
        image: Any,
        *,
        conf_threshold: float = 0.25,
    ) -> DetectionResult:
        arr = _to_grayscale(image)
        h, w = arr.shape
        mask = _otsu(arr)
        labels = _label_connected_components(mask)
        boxes: list[BoundingBox] = []
        max_area = 1
        per_label_stats: dict[int, tuple[int, int, int, int, int]] = {}
        for lab in range(1, labels.max() + 1):
            ys, xs = np.where(labels == lab)
            if ys.size == 0:
                continue
            y0, y1 = int(ys.min()), int(ys.max())
            x0, x1 = int(xs.min()), int(xs.max())
            area = int(ys.size)
            max_area = max(max_area, area)
            per_label_stats[lab] = (x0, y0, x1, y1, area)

        for x0, y0, x1, y1, area in per_label_stats.values():
            confidence = min(1.0, area / max_area)
            if confidence < conf_threshold:
                continue
            boxes.append(
                BoundingBox(
                    x=float(x0),
                    y=float(y0),
                    w=float(max(1, x1 - x0 + 1)),
                    h=float(max(1, y1 - y0 + 1)),
                    class_name=self._class_name,
                    confidence=confidence,
                )
            )
        return DetectionResult(
            boxes=tuple(boxes),
            image_width=w,
            image_height=h,
            model_id=self.id,
            resolved_model_id=self.id,
        )


# --- small pure-numpy helpers -------------------------------------------------


def _to_grayscale(image: Any) -> np.ndarray:
    arr = np.asarray(image)
    if arr.ndim == 3:
        # RGB or RGBA → luminance.
        channels = arr.shape[-1]
        if channels == 4:
            arr = arr[..., :3]
        return (0.2989 * arr[..., 0] + 0.5870 * arr[..., 1] + 0.1140 * arr[..., 2]).astype(
            np.float32
        )
    if arr.ndim == 2:
        return arr.astype(np.float32)
    raise ValueError(f"image must be 2-D or 3-D; got shape {arr.shape}")


def _otsu(gray: np.ndarray) -> np.ndarray:
    """Binary mask: True where pixel > Otsu threshold."""
    g = gray.astype(np.float64)
    hist, edges = np.histogram(g, bins=256, range=(g.min(), g.max() + 1e-6))
    total = hist.sum()
    if total == 0:
        return np.zeros_like(gray, dtype=bool)
    omega = np.cumsum(hist) / total
    mu = np.cumsum(hist * (edges[:-1] + edges[1:]) / 2) / total
    mu_t = mu[-1]
    with np.errstate(divide="ignore", invalid="ignore"):
        sigma_b = (mu_t * omega - mu) ** 2 / np.where(
            omega * (1 - omega) > 0, omega * (1 - omega), 1.0
        )
    threshold = edges[np.argmax(sigma_b)]
    return gray > threshold


def _label_connected_components(mask: np.ndarray) -> np.ndarray:
    """Flood-fill connected-components (4-connectivity). Pure numpy
    iteration — slow on huge masks but fine for the 512x512 test
    tiles we use."""
    labels = np.zeros(mask.shape, dtype=np.int32)
    current_label = 0
    h, w = mask.shape
    for y in range(h):
        for x in range(w):
            if not mask[y, x] or labels[y, x] != 0:
                continue
            current_label += 1
            # Iterative BFS flood-fill.
            stack: list[tuple[int, int]] = [(y, x)]
            while stack:
                yy, xx = stack.pop()
                if yy < 0 or yy >= h or xx < 0 or xx >= w:
                    continue
                if not mask[yy, xx] or labels[yy, xx] != 0:
                    continue
                labels[yy, xx] = current_label
                stack.extend([(yy + 1, xx), (yy - 1, xx), (yy, xx + 1), (yy, xx - 1)])
    return labels
