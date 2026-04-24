"""Model-card safety-v1 contract."""

from __future__ import annotations

import pytest

from openpathai.models.cards import (
    ModelCard,
    ModelCitation,
    ModelSource,
)
from openpathai.models.registry import ModelRegistry
from openpathai.safety import validate_card


def _complete_card(**overrides) -> ModelCard:
    defaults: dict = {
        "name": "fixture",
        "display_name": "Fixture",
        "family": "resnet",
        "source": ModelSource(
            framework="timm",
            identifier="fixture",
            license="MIT",
        ),
        "num_params_m": 1.0,
        "citation": ModelCitation(text="Fixture et al., 2026."),
        "training_data": "ImageNet-1k",
        "intended_use": "Transfer-learning smoke tests.",
        "out_of_scope_use": "Anything real.",
        "known_biases": ("Synthetic data only.",),
    }
    defaults.update(overrides)
    return ModelCard(**defaults)


def test_shipped_cards_all_valid() -> None:
    reg = ModelRegistry(include_user=False)
    assert reg.names(), "expected at least one shipped card"
    for card in reg:
        assert validate_card(card) == [], f"shipped card {card.name} violated the safety contract"


def test_missing_training_data() -> None:
    issues = validate_card(_complete_card(training_data=""))
    codes = {i.code for i in issues}
    assert codes == {"training_data_missing"}


def test_missing_intended_use() -> None:
    issues = validate_card(_complete_card(intended_use=""))
    assert {i.code for i in issues} == {"intended_use_missing"}


def test_missing_out_of_scope_use() -> None:
    issues = validate_card(_complete_card(out_of_scope_use=""))
    assert {i.code for i in issues} == {"out_of_scope_use_missing"}


def test_missing_known_biases() -> None:
    issues = validate_card(_complete_card(known_biases=()))
    assert {i.code for i in issues} == {"known_biases_missing"}


def test_whitespace_only_fields_are_missing() -> None:
    issues = validate_card(_complete_card(training_data="   ", intended_use="\n"))
    codes = {i.code for i in issues}
    assert "training_data_missing" in codes
    assert "intended_use_missing" in codes


def test_blank_bias_entry_fails() -> None:
    issues = validate_card(_complete_card(known_biases=("",)))
    assert any(i.code == "known_biases_missing" for i in issues)


def test_registry_excludes_invalid_card(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Point the user directory at a temp dir and drop an incomplete card in.
    monkeypatch.setenv("OPENPATHAI_HOME", str(tmp_path))
    user_dir = tmp_path / "models"
    user_dir.mkdir()
    (user_dir / "ghost.yaml").write_text(
        """\
name: ghost
display_name: Ghost (test)
family: resnet
source:
  framework: timm
  identifier: ghost
  license: MIT
num_params_m: 0.5
citation:
  text: "placeholder citation"
""",
        encoding="utf-8",
    )
    reg = ModelRegistry(include_repo=False)
    assert "ghost" not in reg.names()
    assert "ghost" in reg.invalid_names()
    issues = reg.invalid_issues("ghost")
    codes = {i.code for i in issues}
    # ghost is missing training_data, intended_use, out_of_scope_use, known_biases
    assert codes == {
        "training_data_missing",
        "intended_use_missing",
        "out_of_scope_use_missing",
        "known_biases_missing",
    }


def test_registry_strict_mode_raises(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENPATHAI_HOME", str(tmp_path))
    monkeypatch.setenv("OPENPATHAI_STRICT_MODEL_CARDS", "1")
    user_dir = tmp_path / "models"
    user_dir.mkdir()
    (user_dir / "ghost.yaml").write_text(
        """\
name: ghost
display_name: Ghost (test)
family: resnet
source:
  framework: timm
  identifier: ghost
  license: MIT
num_params_m: 0.5
citation:
  text: "placeholder citation"
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="safety-contract"):
        ModelRegistry(include_repo=False)
