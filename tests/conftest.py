"""Shared pytest fixtures for OpenPathAI.

A synthetic WSI fixture is generated on demand so no binary blobs need
to be committed to the repo. See ``tests/fixtures/README.md`` for
rationale.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences so substring checks survive
    Typer/Rich's colourised help output on CI (``FORCE_COLOR=1``).
    """
    return _ANSI_RE.sub("", text)


@pytest.fixture()
def clean_stdout():
    """Return a helper that strips ANSI from a ``CliRunner.Result.stdout``."""
    return strip_ansi


@pytest.fixture(scope="session")
def fixtures_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("openpathai-fixtures")


@pytest.fixture(scope="session")
def synthetic_he_tile() -> np.ndarray:
    """A small synthetic H&E-like RGB tile.

    The tile has a central pink/purple blob on a near-white background
    — just enough structure for Otsu and Macenko to fit stably without
    pulling in real pathology images.
    """
    rng = np.random.default_rng(seed=42)
    h, w = 256, 256
    image = np.full((h, w, 3), 240, dtype=np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    radius = np.sqrt((xx - w / 2) ** 2 + (yy - h / 2) ** 2)
    tissue = radius < 90

    # H stain tone (blue-purple) for nuclei.
    image[tissue] = np.array([140, 80, 180], dtype=np.float32)
    # E stain tone (pink) halo.
    halo = (radius >= 60) & (radius < 90)
    image[halo] = np.array([210, 130, 170], dtype=np.float32)

    # Mild random noise so the histograms have texture for Otsu.
    image += rng.normal(loc=0.0, scale=5.0, size=image.shape)
    image = np.clip(image, 0.0, 255.0).astype(np.uint8)
    return image


@pytest.fixture(scope="session")
def synthetic_slide_path(fixtures_dir: Path, synthetic_he_tile: np.ndarray) -> Path:
    """A multi-tile synthetic 'slide' saved as a regular TIFF.

    Pillow's TIFF writer produces a single-layer file; the
    PillowSlideReader is designed exactly for this fallback.
    """
    h, w = 1024, 1024
    canvas = np.full((h, w, 3), 240, dtype=np.uint8)
    # Lay two H&E blobs at different locations so tiling exercises
    # more than one mask region.
    for cy, cx in ((256, 256), (768, 640)):
        yy, xx = np.mgrid[0:h, 0:w]
        radius = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        ring = radius < 120
        canvas[ring] = np.array([150, 90, 180], dtype=np.uint8)

    path = fixtures_dir / "sample_slide.tiff"
    Image.fromarray(canvas).save(path, format="TIFF")
    return path
