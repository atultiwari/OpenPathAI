"""Integration test — train via the pipeline executor and verify caching.

The test only runs when torch is available. A small custom adapter is
registered so the test does not pull in timm (the timm wheels are large
and Phase 3's test matrix stays lean).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

torch_missing = importlib.util.find_spec("torch") is None
pytestmark = pytest.mark.skipif(torch_missing, reason="torch not installed")


@pytest.fixture(autouse=True)
def _clean_batches() -> None:
    from openpathai.training import clear_batches

    clear_batches()
    yield
    clear_batches()


def _monkeypatched_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install a minimal numpy-logit adapter for the test run."""
    import torch
    import torch.nn as nn

    class _StubModel(nn.Module):
        def __init__(self, num_classes: int) -> None:
            super().__init__()
            self.flatten = nn.Flatten()
            self.head = nn.Linear(3 * 32 * 32, num_classes)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            return self.head(self.flatten(x))

    class _StubAdapter:
        framework = "timm"

        def supports(self, card: Any) -> bool:
            return True

        def build(self, card: Any, *, num_classes: int, pretrained: bool = True) -> nn.Module:
            del card, pretrained
            return _StubModel(num_classes)

        def preprocessing(self, card: Any) -> dict[str, Any]:
            return {"input_size": card.input_size, "mean": (0.0,) * 3, "std": (1.0,) * 3}

    from openpathai.models import adapter as adapter_module

    monkeypatch.setattr(adapter_module, "adapter_for_card", lambda card: _StubAdapter())
    # The engine imports the symbol into its namespace; patch that too.
    from openpathai.training import engine as engine_module

    monkeypatch.setattr(engine_module, "adapter_for_card", lambda card: _StubAdapter())


def test_training_pipeline_end_to_end(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _monkeypatched_adapter(monkeypatch)

    from openpathai import (
        ContentAddressableCache,
        Executor,
        Pipeline,
        PipelineStep,
    )
    from openpathai.training import (
        LossConfig,
        OptimizerConfig,
        TrainingConfig,
        register_batch,
        synthetic_tile_batch,
    )

    train_batch = synthetic_tile_batch(num_classes=4, samples_per_class=8, seed=0)
    val_batch = synthetic_tile_batch(num_classes=4, samples_per_class=4, seed=1)
    train_hash = register_batch(train_batch)
    val_hash = register_batch(val_batch)

    config = TrainingConfig(
        model_card="resnet18",
        num_classes=4,
        epochs=1,
        batch_size=8,
        seed=0,
        device="cpu",
        pretrained=False,
        loss=LossConfig(kind="cross_entropy"),
        optimizer=OptimizerConfig(lr=1e-2),
    )

    cache = ContentAddressableCache(root=tmp_path / "cache")
    executor = Executor(cache)
    pipeline = Pipeline(
        id="phase3-smoke",
        steps=[
            PipelineStep(
                id="train",
                op="training.train",
                inputs={
                    "config": config.model_dump(mode="json"),
                    "train_batch_hash": train_hash,
                    "val_batch_hash": val_hash,
                    "checkpoint_dir": str(tmp_path / "ckpts"),
                },
            )
        ],
    )

    result = executor.run(pipeline)
    assert result.cache_stats.hits == 0
    assert result.cache_stats.misses == 1

    report = result.artifacts["train"]
    assert report.artifact_type == "TrainingReportArtifact"
    assert report.num_classes == 4
    assert report.epochs == 1
    assert report.temperature is not None
    assert report.ece_before_calibration is not None
    assert report.ece_after_calibration is not None
    assert report.final_val_accuracy is not None
    assert report.checkpoint_path is not None
    assert Path(report.checkpoint_path).exists()
    assert len(report.history) == 1

    # Rerun — fully cached.
    rerun = executor.run(pipeline)
    assert rerun.cache_stats.hits == 1
    assert rerun.cache_stats.misses == 0
