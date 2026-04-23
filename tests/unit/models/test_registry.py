"""Unit tests for the model registry."""

from __future__ import annotations

from pathlib import Path

import yaml

from openpathai.models.registry import ModelRegistry

SHIPPED = {
    "resnet18",
    "resnet50",
    "efficientnet_b0",
    "efficientnet_b3",
    "mobilenetv3_small_100",
    "mobilenetv3_large_100",
    "vit_tiny_patch16_224",
    "vit_small_patch16_224",
    "swin_tiny_patch4_window7_224",
    "convnext_tiny",
}


def test_repo_registry_loads_shipped_cards() -> None:
    registry = ModelRegistry(include_user=False)
    assert SHIPPED.issubset(set(registry.names()))


def test_registry_get_and_has() -> None:
    registry = ModelRegistry(include_user=False)
    assert registry.has("resnet18") is True
    assert registry.has("nope") is False
    assert registry.get("resnet18").family == "resnet"


def test_registry_filter_by_family() -> None:
    registry = ModelRegistry(include_user=False)
    vits = registry.filter(family="vit")
    assert {c.name for c in vits} == {
        "vit_tiny_patch16_224",
        "vit_small_patch16_224",
    }


def test_registry_user_override_wins(tmp_path: Path) -> None:
    override_dir = tmp_path / "models"
    override_dir.mkdir()
    payload = {
        "name": "resnet18",
        "display_name": "custom resnet18",
        "family": "resnet",
        "source": {
            "framework": "timm",
            "identifier": "resnet18",
            "license": "Custom",
        },
        "num_params_m": 11.7,
        "citation": {"text": "override"},
    }
    (override_dir / "resnet18.yaml").write_text(yaml.safe_dump(payload))

    registry = ModelRegistry(
        search_paths=[override_dir],
        include_repo=True,
        include_user=False,
    )
    card = registry.get("resnet18")
    assert card.display_name == "custom resnet18"
    assert card.source.license == "Custom"


def test_registry_len_names_and_iter() -> None:
    registry = ModelRegistry(include_user=False)
    names = registry.names()
    assert len(registry) == len(names)
    card_names = {card.name for card in registry}
    assert card_names == set(names)


def test_registry_source_returns_path_for_known_card() -> None:
    registry = ModelRegistry(include_user=False)
    path = registry.source("resnet18")
    assert path.name == "resnet18.yaml"


def test_registry_get_and_source_raise_on_unknown() -> None:
    import pytest

    registry = ModelRegistry(include_user=False)
    with pytest.raises(KeyError):
        registry.get("nope")
    with pytest.raises(KeyError):
        registry.source("nope")


def test_registry_filter_by_framework_and_tier() -> None:
    registry = ModelRegistry(include_user=False)
    timm_cards = registry.filter(framework="timm")
    assert all(c.source.framework == "timm" for c in timm_cards)
    t1_cards = registry.filter(tier="T1")
    assert all(c.tier_compatibility.T1 in {"ok", "slow"} for c in t1_cards)


def test_registry_rejects_non_mapping_yaml(tmp_path: Path) -> None:
    import pytest

    bad_dir = tmp_path / "models"
    bad_dir.mkdir()
    (bad_dir / "not_a_mapping.yaml").write_text("- just\n- a\n- list\n")
    with pytest.raises(ValueError, match="must be a mapping"):
        ModelRegistry(search_paths=[bad_dir], include_repo=False, include_user=False)


def test_registry_rejects_invalid_card_yaml(tmp_path: Path) -> None:
    import pytest

    bad_dir = tmp_path / "models"
    bad_dir.mkdir()
    (bad_dir / "bad.yaml").write_text("name: bad\nfamily: not-a-real-family\n")
    with pytest.raises(ValueError, match="Invalid model card"):
        ModelRegistry(search_paths=[bad_dir], include_repo=False, include_user=False)
