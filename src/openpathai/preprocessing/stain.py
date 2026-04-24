"""Macenko stain normalisation (Macenko et al., 2009).

Pure-numpy implementation. The algorithm:

1. Convert RGB → optical density (OD): ``OD = -log10(I / 255 + eps)``.
2. Keep pixels with OD > ``beta`` (drop near-white background).
3. SVD on the OD covariance to find the 2D plane capturing max
   variance.
4. Project OD samples onto that plane and take robust extreme angles
   (``alpha`` / ``100 - alpha`` percentiles) → stain vectors for
   haematoxylin and eosin.
5. Solve ``OD = stain @ concentrations`` for concentrations via
   least-squares.
6. Transform by normalising concentrations to reference maxima, then
   reconstruct with reference stain vectors.

Reference values follow the original paper; they are overridable per-
instance so users can fit to a template slide.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "MacenkoNormalizer",
    "MacenkoStainMatrix",
]


class _MacenkoDegenerateError(RuntimeError):
    """Internal signal that fitting was not possible (blank input)."""


# Macenko 2009 reference H&E stain matrix (rows are stains H, E; columns R, G, B).
_REFERENCE_STAIN_HE = np.array(
    [
        [0.5626, 0.7201, 0.4062],  # Haematoxylin
        [0.2159, 0.8012, 0.5581],  # Eosin
    ],
    dtype=np.float64,
)
# Reference maximum concentrations for H and E channels.
_REFERENCE_MAX_C = np.array([1.9705, 1.0308], dtype=np.float64)


class MacenkoStainMatrix(BaseModel):
    """Serialisable fitted stain basis."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    stain_matrix: tuple[tuple[float, float, float], tuple[float, float, float]]
    max_concentrations: tuple[float, float]

    @classmethod
    def from_arrays(cls, stain: np.ndarray, max_c: np.ndarray) -> MacenkoStainMatrix:
        return cls(
            stain_matrix=(
                (float(stain[0, 0]), float(stain[0, 1]), float(stain[0, 2])),
                (float(stain[1, 0]), float(stain[1, 1]), float(stain[1, 2])),
            ),
            max_concentrations=(float(max_c[0]), float(max_c[1])),
        )

    def as_array(self) -> tuple[np.ndarray, np.ndarray]:
        return (
            np.asarray(self.stain_matrix, dtype=np.float64),
            np.asarray(self.max_concentrations, dtype=np.float64),
        )


class MacenkoNormalizer(BaseModel):
    """Macenko H&E stain normaliser.

    The normaliser is a plain configuration object; :meth:`fit` and
    :meth:`transform` are the pure functions. An optional fitted
    :attr:`target` can be attached after :meth:`fit` so subsequent
    :meth:`transform` calls normalise to that reference rather than the
    literature default.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    alpha: float = Field(default=1.0, ge=0.0, le=50.0)
    beta: float = Field(default=0.15, ge=0.0, le=1.0)
    intensity_norm: float = Field(default=240.0, gt=0.0)
    target: MacenkoStainMatrix | None = None

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------

    @classmethod
    def from_reference(cls, name: str, **overrides: Any) -> MacenkoNormalizer:
        """Build a normaliser bound to a :class:`StainReference` by name.

        Looks the name up in :func:`openpathai.data.default_stain_registry`
        and attaches the resulting basis as ``target``. Extra keyword
        arguments override the ``alpha`` / ``beta`` / ``intensity_norm``
        constants.
        """
        from openpathai.data.stain_refs import default_stain_registry

        reg = default_stain_registry()
        if not reg.has(name):
            raise KeyError(f"Stain reference {name!r} is not registered")
        ref = reg.get(name)
        stain = np.asarray(ref.stain_matrix, dtype=np.float64)
        max_c = np.asarray(ref.max_concentrations, dtype=np.float64)
        target = MacenkoStainMatrix.from_arrays(stain, max_c)
        return cls(target=target, **overrides)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fit(self, image: np.ndarray) -> MacenkoStainMatrix:
        """Fit stain matrix + reference concentrations from an image."""
        stain_matrix, max_c = self._fit_arrays(image)
        return MacenkoStainMatrix.from_arrays(stain_matrix, max_c)

    def transform(
        self,
        image: np.ndarray,
        *,
        target: MacenkoStainMatrix | None = None,
    ) -> np.ndarray:
        """Return a stain-normalised copy of ``image``.

        The ``target`` argument overrides :attr:`self.target`; if neither
        is set, falls back to the literature H&E reference.
        """
        ref = target if target is not None else self.target
        if ref is None:
            ref_stain = _REFERENCE_STAIN_HE
            ref_max_c = _REFERENCE_MAX_C
        else:
            ref_stain, ref_max_c = ref.as_array()

        try:
            source_stain, _ = self._fit_arrays(image)
        except _MacenkoDegenerateError:
            return np.ascontiguousarray(image.astype(np.uint8))

        h, w, _ = image.shape
        od = self._rgb_to_od(image).reshape(-1, 3)
        concentrations, *_ = np.linalg.lstsq(source_stain.T, od.T, rcond=None)

        # Rescale to reference concentration maxima.
        source_percentile = np.percentile(concentrations, 99, axis=1)
        source_percentile = np.where(source_percentile > 1e-3, source_percentile, 1.0)
        scale = ref_max_c / source_percentile
        concentrations = concentrations * scale[:, None]
        # Clamp concentrations to a sane OD range before reconstructing;
        # 0-20 comfortably covers real H&E tissue (pathology OD is
        # almost always < 4) while guarding against SVD outliers and
        # near-white pixels that would overflow `exp()`.
        concentrations = np.clip(concentrations, 0.0, 20.0)

        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            reconstructed = ref_stain.T @ concentrations
            rgb = self.intensity_norm * np.exp(-reconstructed)
        rgb = np.clip(np.nan_to_num(rgb, nan=255.0, posinf=255.0, neginf=0.0), 0.0, 255.0)
        return rgb.T.reshape(h, w, 3).astype(np.uint8)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _rgb_to_od(self, image: np.ndarray) -> np.ndarray:
        rgb = image.astype(np.float64)
        rgb = np.maximum(rgb, 1.0)  # avoid log(0)
        od = -np.log(rgb / self.intensity_norm)
        return od

    def _fit_arrays(self, image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        if image.ndim != 3 or image.shape[2] not in (3, 4):
            raise ValueError("Macenko fit requires an RGB image")
        rgb = image[..., :3]
        od = self._rgb_to_od(rgb).reshape(-1, 3)
        # Bound OD to a realistic range so a handful of black pixels
        # don't drag the SVD into overflow.
        od = np.clip(od, 0.0, 10.0)

        mask = np.all(od > self.beta, axis=1)
        od_bright = od[mask]
        if od_bright.shape[0] < 16:
            raise _MacenkoDegenerateError("Too few non-background pixels for Macenko fit")

        cov = np.cov(od_bright, rowvar=False)
        _eig_vals, eig_vecs = np.linalg.eigh(cov)
        plane = eig_vecs[:, [-1, -2]]  # top-2 eigenvectors, shape (3, 2)

        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            projected = od_bright @ plane
        angles = np.arctan2(projected[:, 1], projected[:, 0])
        lo = np.percentile(angles, self.alpha)
        hi = np.percentile(angles, 100.0 - self.alpha)
        v1 = plane @ np.array([np.cos(lo), np.sin(lo)])
        v2 = plane @ np.array([np.cos(hi), np.sin(hi)])

        # Haematoxylin = stain with higher blue component.
        stain_matrix = np.vstack([v1, v2])
        if stain_matrix[0, 2] < stain_matrix[1, 2]:
            stain_matrix = stain_matrix[::-1, :]
        norms = np.linalg.norm(stain_matrix, axis=1, keepdims=True)
        norms = np.where(norms > 0, norms, 1.0)
        stain_matrix = stain_matrix / norms

        concentrations, *_ = np.linalg.lstsq(stain_matrix.T, od.T, rcond=None)
        max_c = np.percentile(concentrations, 99, axis=1)
        max_c = np.where(max_c > 0, max_c, 1.0)
        return stain_matrix, max_c
