"""Otsu-based tissue masking.

Implementation is deliberately dependency-light — a 256-bin grayscale
histogram followed by the classical between-class variance scan. No
scikit-image dependency at runtime; ``scikit-image`` is installed as an
optional extra and may be used by callers for heavier morphological
operations.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "otsu_threshold",
    "otsu_tissue_mask",
]


def _to_grayscale_uint8(image: np.ndarray) -> np.ndarray:
    """Convert an RGB (H, W, 3) or grayscale (H, W) image to uint8 gray."""
    if image.ndim == 2:
        gray = image
    elif image.ndim == 3 and image.shape[2] in (3, 4):
        rgb = image[..., :3].astype(np.float32)
        # BT.601 luma.
        gray = rgb @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    else:
        raise ValueError(f"Unsupported image shape for grayscale conversion: {image.shape}")

    gray_f = gray.astype(np.float32)
    gray_min = float(np.min(gray_f))
    gray_max = float(np.max(gray_f))
    if gray_max <= 1.0 and gray_min >= 0.0:
        gray_f = gray_f * 255.0
    return np.clip(gray_f, 0.0, 255.0).astype(np.uint8)


def otsu_threshold(image: np.ndarray) -> int:
    """Compute the Otsu threshold (0-255) of a grayscale or RGB image."""
    gray = _to_grayscale_uint8(image)
    hist, _ = np.histogram(gray.ravel(), bins=256, range=(0, 256))
    total = int(hist.sum())
    if total == 0:
        return 0

    # Prefix sums of intensities and counts.
    intensities = np.arange(256, dtype=np.float64)
    cum_w = np.cumsum(hist).astype(np.float64)
    cum_mu = np.cumsum(hist * intensities)

    total_mu = float(cum_mu[-1])
    w_bg = cum_w
    w_fg = total - cum_w
    with np.errstate(divide="ignore", invalid="ignore"):
        mu_bg = np.where(w_bg > 0, cum_mu / np.maximum(w_bg, 1e-9), 0.0)
        mu_fg = np.where(w_fg > 0, (total_mu - cum_mu) / np.maximum(w_fg, 1e-9), 0.0)
        between = w_bg * w_fg * (mu_bg - mu_fg) ** 2

    between = np.nan_to_num(between, nan=-1.0, posinf=-1.0, neginf=-1.0)
    return int(np.argmax(between))


def otsu_tissue_mask(
    image: np.ndarray,
    *,
    invert: bool = True,
    min_threshold: int | None = None,
) -> np.ndarray:
    """Otsu-thresholded tissue mask.

    ``invert=True`` (default) treats darker pixels as tissue and lighter
    pixels as background, which matches H&E / IHC whole-slide images
    where glass appears bright.

    ``min_threshold`` floors the Otsu value — useful on near-blank
    thumbnails where Otsu degenerates and would otherwise declare most
    glass as tissue.
    """
    gray = _to_grayscale_uint8(image)
    t = otsu_threshold(gray)
    if min_threshold is not None:
        t = max(t, int(min_threshold))
    if invert:
        return gray <= t
    return gray > t
