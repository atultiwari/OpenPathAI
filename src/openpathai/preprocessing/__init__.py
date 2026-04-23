"""Preprocessing primitives: stain normalisation and tissue masking.

These are the first data-layer operations pathology pipelines lean on:

* :class:`~openpathai.preprocessing.stain.MacenkoNormalizer` — Macenko
  stain normalisation (Macenko et al., 2009) in pure numpy, no external
  stain libraries required.
* :func:`~openpathai.preprocessing.mask.otsu_tissue_mask` — Otsu-
  thresholded tissue mask from a thumbnail or tile.
"""

from __future__ import annotations

from openpathai.preprocessing.mask import otsu_threshold, otsu_tissue_mask
from openpathai.preprocessing.stain import MacenkoNormalizer, MacenkoStainMatrix

__all__ = [
    "MacenkoNormalizer",
    "MacenkoStainMatrix",
    "otsu_threshold",
    "otsu_tissue_mask",
]
