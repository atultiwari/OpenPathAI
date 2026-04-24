"""FoundationAdapter protocol conformance across every shipped adapter."""

from __future__ import annotations

import pytest

from openpathai.foundation import FoundationAdapter, default_foundation_registry


@pytest.fixture
def registry():
    return default_foundation_registry()


def test_registry_ships_eight_adapters(registry) -> None:
    names = registry.names()
    assert len(names) == 8
    assert "dinov2_vits14" in names
    assert "uni" in names
    assert "ctranspath" in names
    # Stubs too.
    for stub in ("uni2_h", "conch", "virchow2", "prov_gigapath", "hibou"):
        assert stub in names


def test_every_adapter_matches_protocol_attrs(registry) -> None:
    for adapter in registry:
        # Attribute surface.
        for attr in (
            "id",
            "display_name",
            "gated",
            "hf_repo",
            "input_size",
            "embedding_dim",
            "tier_compatibility",
            "vram_gb",
            "license",
            "citation",
        ):
            assert hasattr(adapter, attr), f"{adapter.id} missing {attr}"
        # Method surface.
        for method in ("build", "preprocess", "embed"):
            assert callable(getattr(adapter, method)), f"{adapter.id} missing callable {method}"


def test_every_adapter_id_unique(registry) -> None:
    ids = [a.id for a in registry]
    assert len(ids) == len(set(ids))


def test_only_dinov2_is_open(registry) -> None:
    for a in registry:
        if a.id == "dinov2_vits14":
            assert a.gated is False
        else:
            # Every other shipped adapter is gated in some form
            # (HF gated or user-supplied weights).
            assert a.gated is True


def test_runtime_protocol_check(registry) -> None:
    for adapter in registry:
        assert isinstance(adapter, FoundationAdapter)


def test_embedding_dims_are_positive(registry) -> None:
    for a in registry:
        assert a.embedding_dim >= 1
        assert a.input_size == (224, 224)
        assert a.tier_compatibility  # non-empty set


def test_registry_double_register_raises(registry) -> None:
    from openpathai.foundation.dinov2 import DINOv2SmallAdapter

    with pytest.raises(ValueError, match="already registered"):
        registry.register(DINOv2SmallAdapter())


def test_registry_get_missing_raises(registry) -> None:
    with pytest.raises(KeyError, match="unknown"):
        registry.get("does_not_exist")
