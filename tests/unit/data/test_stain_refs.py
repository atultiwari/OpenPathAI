"""Stain-reference registry + ``MacenkoNormalizer.from_reference``."""

from __future__ import annotations

import numpy as np
import pytest

from openpathai.data import StainReference, StainReferenceRegistry, default_stain_registry
from openpathai.preprocessing import MacenkoNormalizer


def test_shipped_registry_exposes_the_four_refs() -> None:
    reg = default_stain_registry()
    names = reg.names()
    for expected in ("he_default", "he_colon", "he_breast", "he_lung"):
        assert expected in names


def test_every_shipped_card_parses() -> None:
    reg = default_stain_registry()
    for ref in reg:
        assert isinstance(ref, StainReference)
        assert len(ref.stain_matrix) == 2
        assert len(ref.max_concentrations) == 2
        assert ref.license


def test_he_default_matches_macenko_constants() -> None:
    ref = default_stain_registry().get("he_default")
    np.testing.assert_allclose(
        np.asarray(ref.stain_matrix, dtype=np.float64),
        np.array([[0.5626, 0.7201, 0.4062], [0.2159, 0.8012, 0.5581]]),
        atol=1e-6,
    )
    np.testing.assert_allclose(
        np.asarray(ref.max_concentrations, dtype=np.float64),
        np.array([1.9705, 1.0308]),
        atol=1e-6,
    )


def test_macenko_from_reference_binds_target() -> None:
    normaliser = MacenkoNormalizer.from_reference("he_default")
    assert normaliser.target is not None
    stain = np.asarray(normaliser.target.stain_matrix, dtype=np.float64)
    assert stain.shape == (2, 3)


def test_macenko_from_reference_unknown_raises() -> None:
    with pytest.raises(KeyError, match="not registered"):
        MacenkoNormalizer.from_reference("nope")


def test_registry_rejects_non_mapping_yaml(tmp_path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("- just\n- a\n- list\n")
    with pytest.raises(ValueError, match="must be a mapping"):
        StainReferenceRegistry(
            search_paths=[tmp_path],
            include_repo=False,
            include_user=False,
        )


def test_registry_user_override_wins(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPENPATHAI_HOME", str(tmp_path))
    user_dir = tmp_path / "stain_references"
    user_dir.mkdir()
    (user_dir / "he_default.yaml").write_text(
        """
name: he_default
display_name: overridden
stain_kind: "H&E"
tissue: [custom]
stain_matrix:
  - [0.1, 0.2, 0.3]
  - [0.4, 0.5, 0.6]
max_concentrations: [1.0, 1.0]
license: "MIT"
citation:
  text: "override fixture"
""",
        encoding="utf-8",
    )
    reg = StainReferenceRegistry(include_repo=False)
    assert reg.get("he_default").display_name == "overridden"
