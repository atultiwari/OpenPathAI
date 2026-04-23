"""``openpathai train`` subcommand — Tier-A supervised training."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer


def register(app: typer.Typer) -> None:
    @app.command()
    def train(  # pragma: no cover - torch-gated; smoke covered by test_cli_smoke
        model: Annotated[str, typer.Option(help="Model card name, e.g. resnet18.")],
        num_classes: Annotated[int, typer.Option(min=1, help="Number of classes.")],
        epochs: Annotated[int, typer.Option(min=1, help="Training epochs.")] = 1,
        batch_size: Annotated[int, typer.Option(min=1, help="Batch size.")] = 16,
        seed: Annotated[int, typer.Option(help="Deterministic seed.")] = 0,
        device: Annotated[
            str,
            typer.Option(help="Device: auto, cpu, cuda, mps."),
        ] = "auto",
        loss: Annotated[
            str,
            typer.Option(help="Loss kind: cross_entropy, weighted_cross_entropy, focal, ldam."),
        ] = "cross_entropy",
        lr: Annotated[float, typer.Option(min=0.0, help="Initial learning rate.")] = 1e-3,
        output_dir: Annotated[
            Path | None,
            typer.Option(help="Directory for checkpoints + report JSON."),
        ] = None,
        synthetic: Annotated[
            bool,
            typer.Option(
                "--synthetic",
                help="Train on a tiny synthetic multi-class tile batch (Phase 3 smoke path).",
            ),
        ] = False,
    ) -> None:
        """Train a Tier-A tile classifier.

        Phase 3 wired the ``--synthetic`` path end-to-end. Real-cohort
        training still awaits the Phase 5 dataset-driven loader, which
        will hook ``openpathai.data`` into this command when ready.
        """
        from openpathai.models import default_model_registry
        from openpathai.training import (
            LossConfig,
            OptimizerConfig,
            TrainingConfig,
            synthetic_tile_batch,
        )
        from openpathai.training.engine import LightningTrainer

        if not synthetic:
            typer.echo(
                "Real-cohort training plugs into Phase 5's dataset driver "
                "(in flight). For now, re-run with --synthetic to exercise "
                "the engine end-to-end."
            )
            raise typer.Exit(2)

        registry = default_model_registry()
        if not registry.has(model):
            typer.echo(f"Model card {model!r} is not registered.", err=True)
            raise typer.Exit(2)
        card = registry.get(model)

        config = TrainingConfig(
            model_card=model,
            num_classes=num_classes,
            epochs=epochs,
            batch_size=batch_size,
            seed=seed,
            device=device,  # type: ignore[arg-type]
            pretrained=False,
            loss=LossConfig(kind=loss),  # type: ignore[arg-type]
            optimizer=OptimizerConfig(lr=lr),
        )

        train_batch = synthetic_tile_batch(num_classes=num_classes, seed=seed)
        val_batch = synthetic_tile_batch(num_classes=num_classes, seed=seed + 1)
        trainer = LightningTrainer(
            config,
            card=card,
            checkpoint_dir=output_dir,
        )
        report = trainer.fit(train=train_batch, val=val_batch)
        if output_dir is not None:
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "report.json").write_text(
                report.model_dump_json(indent=2),
                encoding="utf-8",
            )
        typer.echo(json.dumps(report.model_dump(mode="json"), indent=2, default=str))


__all__ = ["register"]
