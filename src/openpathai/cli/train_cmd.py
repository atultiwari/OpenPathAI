"""``openpathai train`` subcommand — Tier-A supervised training.

Phase 9 extends the original Phase 3 ``--synthetic`` path with two
real data sources:

* ``--dataset CARD``  → any registered dataset card with
  ``download.method == "local"`` (Phase 7 local datasets +
  ``kather_crc_5k`` once downloaded).
* ``--cohort PATH``  → a cohort YAML; labels come from
  ``SlideRef.label`` on each slide. ``--class-name`` may be repeated
  to pin an explicit label set; otherwise the distinct labels seen in
  the cohort are used.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer


def register(app: typer.Typer) -> None:
    @app.command()
    def train(  # pragma: no cover - torch-gated; smoke covered by test_cli_smoke
        model: Annotated[str, typer.Option(help="Model card name, e.g. resnet18.")],
        num_classes: Annotated[
            int,
            typer.Option(
                min=1, help="Number of classes (inferred from card/cohort when possible)."
            ),
        ] = 2,
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
        dataset: Annotated[
            str | None,
            typer.Option(
                "--dataset",
                help="Dataset card name (local cards only in Phase 9).",
            ),
        ] = None,
        cohort: Annotated[
            Path | None,
            typer.Option(
                "--cohort",
                help="Cohort YAML path. Labels come from SlideRef.label.",
            ),
        ] = None,
        class_name: Annotated[
            list[str] | None,
            typer.Option(
                "--class-name",
                help="Repeat to pin an explicit class list (cohort mode).",
            ),
        ] = None,
        tile_size: Annotated[
            int,
            typer.Option(
                "--tile-size",
                min=16,
                max=2048,
                help="Tile edge size (square).",
            ),
        ] = 224,
        no_audit: Annotated[
            bool,
            typer.Option(
                "--no-audit",
                help="Skip the Phase 8 audit log write for this run.",
            ),
        ] = False,
    ) -> None:
        """Train a Tier-A tile classifier.

        Exactly one of ``--synthetic``, ``--dataset``, or ``--cohort``
        must be supplied. ``--synthetic`` runs the Phase 3 smoke path;
        ``--dataset`` pulls from a local dataset card; ``--cohort``
        iterates a cohort YAML.
        """
        sources = sum(1 for x in (synthetic, dataset is not None, cohort is not None) if x)
        if sources != 1:
            typer.secho(
                "Pass exactly one of --synthetic, --dataset NAME, or --cohort PATH.",
                fg="red",
                err=True,
            )
            raise typer.Exit(2)

        from openpathai.models import default_model_registry
        from openpathai.training import (
            LossConfig,
            OptimizerConfig,
            TrainingConfig,
            synthetic_tile_batch,
        )
        from openpathai.training.engine import LightningTrainer

        registry = default_model_registry()
        if not registry.has(model):
            typer.echo(f"Model card {model!r} is not registered.", err=True)
            raise typer.Exit(2)
        card = registry.get(model)

        # ------------------------------------------------------------------
        # Build train / val datasets for the selected source.
        # ------------------------------------------------------------------
        train_data: object
        val_data: object | None
        data_source_blurb: str
        if synthetic:
            train_data = synthetic_tile_batch(num_classes=num_classes, seed=seed)
            val_data = synthetic_tile_batch(num_classes=num_classes, seed=seed + 1)
            data_source_blurb = "synthetic"
        elif dataset is not None:
            from openpathai.data import default_registry
            from openpathai.training import build_torch_dataset_from_card

            card_registry = default_registry()
            if not card_registry.has(dataset):
                typer.secho(
                    f"Dataset card {dataset!r} is not registered.",
                    fg="red",
                    err=True,
                )
                raise typer.Exit(2)
            dataset_card = card_registry.get(dataset)
            num_classes = dataset_card.num_classes
            try:
                train_data = build_torch_dataset_from_card(
                    dataset_card,
                    tile_size=(tile_size, tile_size),
                )
            except NotImplementedError as exc:
                typer.secho(str(exc), fg="red", err=True)
                raise typer.Exit(2) from exc
            val_data = None  # Phase 9 uses the same tree for train; Phase 10 splits.
            data_source_blurb = f"dataset={dataset_card.name}"
        else:
            assert cohort is not None
            from openpathai.io import Cohort
            from openpathai.training import build_torch_dataset_from_cohort

            try:
                loaded_cohort = Cohort.from_yaml(cohort)
            except (ValueError, FileNotFoundError) as exc:
                typer.secho(f"Failed to load cohort: {exc}", fg="red", err=True)
                raise typer.Exit(2) from exc
            if class_name:
                classes = tuple(class_name)
            else:
                seen = {s.label for s in loaded_cohort.slides if s.label is not None}
                classes = tuple(sorted(seen))
            num_classes = len(classes)
            if num_classes < 2:
                typer.secho(
                    "Cohort must carry at least 2 distinct slide labels, "
                    f"got {num_classes}. Pass --class-name to pin the label set.",
                    fg="red",
                    err=True,
                )
                raise typer.Exit(2)
            train_data = build_torch_dataset_from_cohort(
                loaded_cohort,
                class_names=classes,
                tile_size=(tile_size, tile_size),
            )
            val_data = None
            data_source_blurb = f"cohort={loaded_cohort.id}"

        typer.echo(f"source: {data_source_blurb}   num_classes={num_classes}")

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

        trainer = LightningTrainer(
            config,
            card=card,
            checkpoint_dir=output_dir,
        )
        report = trainer.fit(train=train_data, val=val_data)

        if output_dir is not None:
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "report.json").write_text(
                report.model_dump_json(indent=2),
                encoding="utf-8",
            )
        typer.echo(json.dumps(report.model_dump(mode="json"), indent=2, default=str))

        if not no_audit:
            from openpathai.safety.audit import log_training

            run_id = log_training(
                model_id=model,
                metrics={
                    "source": data_source_blurb,
                    "num_classes": num_classes,
                    "epochs": epochs,
                    "batch_size": batch_size,
                    "loss": loss,
                    "lr": lr,
                    "seed": seed,
                    "final_val_accuracy": report.final_val_accuracy,
                    "ece_before_calibration": report.ece_before_calibration,
                    "ece_after_calibration": report.ece_after_calibration,
                },
                manifest_path=str(output_dir / "report.json") if output_dir else "",
            )
            if run_id:
                typer.echo(f"audit: {run_id}")


__all__ = ["register"]
