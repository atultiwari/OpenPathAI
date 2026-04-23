"""Unit tests for ``openpathai.pipeline.schema``."""

from __future__ import annotations

import pytest

from openpathai.pipeline.schema import (
    Artifact,
    IntArtifact,
    StringArtifact,
    canonical_json,
    canonical_sha256,
)


@pytest.mark.unit
def test_canonical_json_is_deterministic_across_key_order() -> None:
    a = {"b": 2, "a": 1, "c": 3}
    b = {"a": 1, "c": 3, "b": 2}
    assert canonical_json(a) == canonical_json(b)


@pytest.mark.unit
def test_canonical_sha256_is_stable() -> None:
    digest1 = canonical_sha256({"x": 1, "y": [1, 2, 3]})
    digest2 = canonical_sha256({"y": [1, 2, 3], "x": 1})
    assert digest1 == digest2
    assert len(digest1) == 64  # SHA-256 hex


@pytest.mark.unit
def test_int_artifact_content_hash_matches_for_equal_values() -> None:
    a = IntArtifact(value=42)
    b = IntArtifact(value=42)
    assert a.content_hash() == b.content_hash()


@pytest.mark.unit
def test_int_artifact_content_hash_differs_for_different_values() -> None:
    assert IntArtifact(value=42).content_hash() != IntArtifact(value=43).content_hash()


@pytest.mark.unit
def test_artifact_is_frozen() -> None:
    a = IntArtifact(value=1)
    with pytest.raises(Exception):  # noqa: B017 — pydantic raises ValidationError
        a.value = 2  # type: ignore[misc]


@pytest.mark.unit
def test_artifact_type_name_round_trips() -> None:
    assert IntArtifact(value=1).artifact_type == "IntArtifact"
    assert StringArtifact(value="x").artifact_type == "StringArtifact"


@pytest.mark.unit
def test_artifact_type_is_baked_into_hash() -> None:
    """Two artifact types with the same field values should hash differently."""

    class AlphaArtifact(Artifact):
        value: int

    class BetaArtifact(Artifact):
        value: int

    alpha = AlphaArtifact(value=1)
    beta = BetaArtifact(value=1)
    assert alpha.content_hash() != beta.content_hash()
