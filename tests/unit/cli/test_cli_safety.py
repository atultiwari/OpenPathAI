"""Unit tests for the Phase 7 safety CLI surfaces.

* ``openpathai models check`` — validates every registered card against
  the safety-v1 contract.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from openpathai.cli.main import app

runner = CliRunner()


@pytest.mark.unit
def test_models_check_all_shipped_cards_pass() -> None:
    result = runner.invoke(app, ["models", "check"])
    assert result.exit_code == 0, result.stdout
    for name in (
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
    ):
        assert f"ok   {name}" in result.stdout or f"ok   {name}\n" in result.stdout


@pytest.mark.unit
def test_models_check_flags_incomplete_user_card(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENPATHAI_HOME", str(tmp_path))
    user_dir = tmp_path / "models"
    user_dir.mkdir()
    (user_dir / "bad.yaml").write_text(
        """\
name: bad
display_name: Bad (test)
family: resnet
source:
  framework: timm
  identifier: bad
  license: MIT
num_params_m: 0.5
citation:
  text: "placeholder"
""",
        encoding="utf-8",
    )
    # Reset the global registry cache so the new user dir is picked up.
    import openpathai.models.registry as registry_mod

    registry_mod._DEFAULT_REGISTRY = None  # type: ignore[attr-defined]

    result = runner.invoke(app, ["models", "check"])
    registry_mod._DEFAULT_REGISTRY = None  # type: ignore[attr-defined]

    assert result.exit_code == 2
    assert "FAIL bad" in result.stdout
    assert "training_data_missing" in result.stdout
