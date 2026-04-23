"""Shared numpy helpers for every explainer.

None of these functions depend on torch. They handle heatmap
normalisation, resizing, PNG encoding/decoding, and overlaying a
heatmap on a tile — building blocks the GUI (Phase 6), the PDF report
(Phase 7), and the DZI overlay (Phase 9) all reuse.
"""

from __future__ import annotations

import base64
import io

import numpy as np
from PIL import Image

__all__ = [
    "decode_png",
    "encode_png",
    "heatmap_to_rgb",
    "normalise_01",
    "overlay_on_tile",
    "resize_heatmap",
]


def normalise_01(heatmap: np.ndarray) -> np.ndarray:
    """Scale an array into ``[0, 1]`` by its min/max.

    A constant array is returned as zeros (rather than NaN). The
    output dtype is always ``float32``.
    """
    arr = np.asarray(heatmap, dtype=np.float32)
    lo = float(np.min(arr))
    hi = float(np.max(arr))
    if hi - lo <= 0.0:
        return np.zeros_like(arr)
    return (arr - lo) / (hi - lo)


def resize_heatmap(
    heatmap: np.ndarray,
    *,
    size: tuple[int, int],
) -> np.ndarray:
    """Resize a 2D heatmap to ``(height, width)`` via bilinear interp.

    Delegates to Pillow so the result matches what the GUI + PDF
    renderers expect. The heatmap is clamped to ``[0, 1]`` before and
    after so the PNG encode step has a stable domain.
    """
    if heatmap.ndim != 2:
        raise ValueError(f"heatmap must be 2D; got shape {heatmap.shape}")
    height, width = size
    if height < 1 or width < 1:
        raise ValueError(f"size must be positive; got {size}")
    clamped = np.clip(heatmap.astype(np.float32), 0.0, 1.0)
    img = Image.fromarray((clamped * 255).astype(np.uint8), mode="L")
    resized = img.resize((width, height), resample=Image.Resampling.BILINEAR)
    return np.asarray(resized, dtype=np.float32) / 255.0


def heatmap_to_rgb(heatmap: np.ndarray) -> np.ndarray:
    """Convert a ``[0, 1]`` grayscale heatmap to an RGB magma-style map.

    A numpy-only approximation of matplotlib's *magma* colour map: good
    enough for a tile overlay without pulling matplotlib in as a
    runtime dependency.
    """
    if heatmap.ndim != 2:
        raise ValueError(f"heatmap must be 2D; got shape {heatmap.shape}")
    values = np.clip(heatmap.astype(np.float32), 0.0, 1.0)
    r = np.clip(1.5 * values - 0.1, 0.0, 1.0)
    g = np.clip(2.0 * (values - 0.3), 0.0, 1.0)
    b = np.clip(1.5 * (values - 0.6), 0.0, 1.0)
    rgb = np.stack([r, g, b], axis=-1)
    return (rgb * 255).astype(np.uint8)


def overlay_on_tile(
    tile: np.ndarray,
    heatmap: np.ndarray,
    *,
    alpha: float = 0.45,
) -> np.ndarray:
    """Blend a heatmap onto an RGB tile.

    ``tile`` is a ``(H, W, 3)`` uint8 array and ``heatmap`` is a
    ``[0, 1]`` 2D float array sized to the tile. Returns a uint8
    ``(H, W, 3)`` array.
    """
    if tile.ndim != 3 or tile.shape[-1] != 3:
        raise ValueError(f"tile must be (H, W, 3); got {tile.shape}")
    if heatmap.ndim != 2:
        raise ValueError(f"heatmap must be 2D; got {heatmap.shape}")
    if tile.shape[:2] != heatmap.shape:
        raise ValueError(
            f"tile and heatmap disagree on spatial size: {tile.shape[:2]} vs {heatmap.shape}"
        )
    if not 0.0 <= alpha <= 1.0:
        raise ValueError(f"alpha must be in [0, 1]; got {alpha}")
    colour = heatmap_to_rgb(heatmap).astype(np.float32)
    base = tile.astype(np.float32)
    out = (1 - alpha) * base + alpha * colour
    return np.clip(out, 0.0, 255.0).astype(np.uint8)


def encode_png(rgb: np.ndarray) -> str:
    """Base64-encode an RGB or grayscale uint8 array as a PNG.

    Metadata (timestamp, pHYs, etc.) is suppressed so the bytes are
    deterministic for a given input array.
    """
    arr = np.asarray(rgb)
    if arr.dtype != np.uint8:
        raise ValueError(f"encode_png expects uint8; got {arr.dtype}")
    mode: str
    if arr.ndim == 2:
        mode = "L"
    elif arr.ndim == 3 and arr.shape[-1] == 3:
        mode = "RGB"
    else:
        raise ValueError(f"encode_png expects (H, W) or (H, W, 3); got {arr.shape}")
    img = Image.fromarray(arr, mode=mode)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False, compress_level=6)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def decode_png(blob: str) -> np.ndarray:
    """Inverse of :func:`encode_png` — decode a base64 PNG to a numpy array."""
    try:
        raw = base64.b64decode(blob.encode("ascii"), validate=True)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("decode_png received an invalid base64 string") from exc
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except Exception as exc:
        raise ValueError("decode_png received bytes that are not a valid PNG") from exc
    return np.asarray(img)
