"""Phase 17 — diagnostic-mode model-pin enforcement."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from openpathai.pipeline.cache import ContentAddressableCache
from openpathai.pipeline.executor import (
    DiagnosticModeError,
    Executor,
    Pipeline,
    PipelineStep,
)
from openpathai.pipeline.node import NodeRegistry


def _init_clean_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            "commit",
            "--allow-empty",
            "-m",
            "seed",
            "-q",
        ],
        cwd=path,
        check=True,
    )


def _fake_registry(card_revision: str | None) -> MagicMock:
    """Build a MagicMock registry where `get("resnet18")` returns a
    card whose ``source.revision`` is either a pinned string or None."""
    source = MagicMock()
    source.revision = card_revision
    card = MagicMock()
    card.source = source
    card.name = "resnet18"
    reg = MagicMock()
    reg.has.side_effect = lambda name: name == "resnet18"
    reg.get.side_effect = lambda name: card
    return reg


@pytest.fixture
def executor(tmp_path: Path) -> Executor:
    cache = ContentAddressableCache(root=tmp_path / "cache")
    return Executor(cache=cache, registry=NodeRegistry())


def _diagnostic_pipeline(model_ref: str = "resnet18") -> Pipeline:
    return Pipeline(
        id="diag-pin",
        mode="diagnostic",  # type: ignore[arg-type]
        steps=[
            PipelineStep(
                id="train",
                op="training.train",
                inputs={"model": model_ref},
            ),
        ],
    )


def test_unpinned_card_rejects_diagnostic_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, executor: Executor
) -> None:
    monkeypatch.chdir(tmp_path)
    _init_clean_repo(tmp_path)
    monkeypatch.delenv("OPENPATHAI_DIAGNOSTIC_SKIP_MODEL_PIN_CHECK", raising=False)
    fake = _fake_registry(card_revision=None)
    monkeypatch.setattr("openpathai.models.default_model_registry", lambda: fake, raising=True)

    with pytest.raises(DiagnosticModeError, match="no pinned"):
        executor._check_diagnostic_preconditions(_diagnostic_pipeline())


def test_pinned_card_accepts_diagnostic_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, executor: Executor
) -> None:
    monkeypatch.chdir(tmp_path)
    _init_clean_repo(tmp_path)
    monkeypatch.delenv("OPENPATHAI_DIAGNOSTIC_SKIP_MODEL_PIN_CHECK", raising=False)
    fake = _fake_registry(card_revision="abc123de")
    monkeypatch.setattr("openpathai.models.default_model_registry", lambda: fake, raising=True)
    # Doesn't raise.
    executor._check_diagnostic_preconditions(_diagnostic_pipeline())


def test_bypass_env_var_skips_pin_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, executor: Executor
) -> None:
    monkeypatch.chdir(tmp_path)
    _init_clean_repo(tmp_path)
    monkeypatch.setenv("OPENPATHAI_DIAGNOSTIC_SKIP_MODEL_PIN_CHECK", "1")
    fake = _fake_registry(card_revision=None)  # unpinned
    monkeypatch.setattr("openpathai.models.default_model_registry", lambda: fake, raising=True)
    # Even though card is unpinned, bypass env var skips the check.
    executor._check_diagnostic_preconditions(_diagnostic_pipeline())


def test_exploratory_mode_skips_pin_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, executor: Executor
) -> None:
    monkeypatch.chdir(tmp_path)
    fake = _fake_registry(card_revision=None)
    monkeypatch.setattr("openpathai.models.default_model_registry", lambda: fake, raising=True)
    pipeline = Pipeline(
        id="exp-no-pin",
        mode="exploratory",
        steps=[PipelineStep(id="s", op="training.train", inputs={"model": "resnet18"})],
    )
    executor._check_diagnostic_preconditions(pipeline)


def test_non_model_step_does_not_trigger_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, executor: Executor
) -> None:
    monkeypatch.chdir(tmp_path)
    _init_clean_repo(tmp_path)
    monkeypatch.delenv("OPENPATHAI_DIAGNOSTIC_SKIP_MODEL_PIN_CHECK", raising=False)
    # Registry never gets queried because no step has a `model` input.
    fake = _fake_registry(card_revision=None)
    monkeypatch.setattr("openpathai.models.default_model_registry", lambda: fake, raising=True)
    pipeline = Pipeline(
        id="diag-no-model",
        mode="diagnostic",  # type: ignore[arg-type]
        steps=[PipelineStep(id="s", op="data.load", inputs={"path": "x"})],
    )
    executor._check_diagnostic_preconditions(pipeline)


def test_unknown_model_id_does_not_trigger_pin_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, executor: Executor
) -> None:
    """If the registry doesn't know the model id, we assume an
    adapter-layer check handles it — we just skip rather than
    blowing up here."""
    monkeypatch.chdir(tmp_path)
    _init_clean_repo(tmp_path)
    fake = _fake_registry(card_revision=None)
    monkeypatch.setattr("openpathai.models.default_model_registry", lambda: fake, raising=True)
    pipeline = Pipeline(
        id="diag-unknown",
        mode="diagnostic",  # type: ignore[arg-type]
        steps=[
            PipelineStep(
                id="s",
                op="training.train",
                inputs={"model": "unknown-model"},
            )
        ],
    )
    executor._check_diagnostic_preconditions(pipeline)
