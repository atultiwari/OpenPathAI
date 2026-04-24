"""Blur QC check — variance of the Laplacian.

Classical blur detector: convolve the image with a 3x3 Laplacian
kernel, take the variance of the response. Sharp images produce high
variance (strong edges), blurred images produce low variance. Pure
numpy; no OpenCV / scikit-image dependency at runtime.
"""

from __future__ import annotations

import numpy as np

from openpathai.preprocessing.qc.findings import QCFinding

__all__ = [
    "DEFAULT_BLUR_THRESHOLD",
    "blur_finding",
    "laplacian_variance",
]


DEFAULT_BLUR_THRESHOLD: float = 80.0
"""Score below this is flagged as blurred.

Empirically tuned on H&E thumbnails at ~2048 px long edge. Callers
with different magnifications should override via ``threshold=``.
"""


_LAPLACIAN_KERNEL = np.array(
    [[0, 1, 0], [1, -4, 1], [0, 1, 0]],
    dtype=np.float32,
)


def _to_grayscale(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image.astype(np.float32)
    if image.ndim == 3 and image.shape[2] >= 3:
        rgb = image[..., :3].astype(np.float32)
        return rgb @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    raise ValueError(f"Unsupported image shape {image.shape} for blur QC")


def _convolve2d(image: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    """Single-channel 2D convolution with edge padding.

    Pure-numpy because scikit-image / scipy are optional extras.
    Restricted to 3x3 kernels (our Laplacian). Edge-padding (not
    zero-padding) avoids a spurious edge response when the input is
    uniformly flat.
    """
    if kernel.shape != (3, 3):
        raise ValueError("kernel must be 3x3")
    pad = np.pad(image, 1, mode="edge")
    h, w = image.shape
    out = np.zeros_like(image, dtype=np.float32)
    for i in range(3):
        for j in range(3):
            out += kernel[i, j] * pad[i : i + h, j : j + w]
    return out


def laplacian_variance(image: np.ndarray) -> float:
    """Return the variance of the Laplacian of ``image``.

    Higher is sharper.
    """
    gray = _to_grayscale(image)
    lap = _convolve2d(gray, _LAPLACIAN_KERNEL)
    return float(np.var(lap))


def blur_finding(
    image: np.ndarray,
    *,
    threshold: float = DEFAULT_BLUR_THRESHOLD,
) -> QCFinding:
    """Run the blur check on ``image`` and return a :class:`QCFinding`."""
    score = laplacian_variance(image)
    passed = score >= threshold
    severity = "info" if passed else "fail"
    if passed:
        message = f"Laplacian variance {score:.1f} ≥ threshold {threshold:.1f} (sharp)."
    else:
        message = (
            f"Laplacian variance {score:.1f} < threshold {threshold:.1f} "
            f"(blurred — low edge energy)."
        )
    return QCFinding(
        check="blur",
        severity=severity,
        score=score,
        passed=passed,
        message=message,
    )
