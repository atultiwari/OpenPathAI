"""OpenPathAI CLI entry point.

Phase 0 registered only ``--version`` and a ``hello`` smoke command.
Phase 3 adds two more: ``openpathai models`` (lists registered model
cards) and ``openpathai train`` (runs the Phase 3 supervised trainer
against a synthetic or registered cohort).

Every heavy import (torch / timm / lightning) happens **inside** a
command callback so ``openpathai --help`` and ``--version`` stay fast
and torch-free.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from openpathai import __version__

app = typer.Typer(
    name="openpathai",
    help="OpenPathAI — computational pathology workflow environment.",
    no_args_is_help=True,
    add_completion=False,
)

models_app = typer.Typer(
    name="models",
    help="Inspect the Tier-A model zoo.",
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(models_app)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit(0)


@app.callback()
def _main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Print the OpenPathAI version and exit.",
    ),
) -> None:
    """Root callback wiring ``--version`` to the top-level command."""
    del version


@app.command()
def hello() -> None:
    """Phase 0 smoke command — prints a liveness message."""
    typer.echo("Phase 0 foundation is live.")


# ---------------------------------------------------------------------------
# Models subcommand (Phase 3)
# ---------------------------------------------------------------------------


@models_app.command("list")
def list_models(
    family: Annotated[
        str | None,
        typer.Option(help="Filter by family (resnet, vit, swin, ...)."),
    ] = None,
    framework: Annotated[
        str | None,
        typer.Option(help="Filter by framework (timm, huggingface, ...)."),
    ] = None,
    tier: Annotated[
        str | None,
        typer.Option(help="Filter by compute tier (T1, T2, T3)."),
    ] = None,
) -> None:
    """List every registered model card, optionally filtered."""
    from openpathai.models import default_model_registry
    from openpathai.models.cards import ModelFamily, ModelFramework

    registry = default_model_registry()
    cards = registry.filter(
        family=family if family is None else _cast_family(family),  # type: ignore[arg-type]
        framework=framework if framework is None else _cast_framework(framework),  # type: ignore[arg-type]
        tier=tier,
    )
    if not cards:
        typer.echo("(no model cards matched)")
        raise typer.Exit(0)
    _ = ModelFamily, ModelFramework  # keep imports tight
    for card in cards:
        typer.echo(
            f"{card.name:36s}  family={card.family:<10s}  "
            f"params={card.num_params_m:6.1f}M  license={card.source.license}"
        )


def _cast_family(value: str) -> str:
    return value


def _cast_framework(value: str) -> str:
    return value


# ---------------------------------------------------------------------------
# Train subcommand (Phase 3)
# ---------------------------------------------------------------------------


@app.command()
def train(
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

    Phase 3 wires only the ``--synthetic`` path end-to-end. Real cohort
    training plugs into Phase 5's CLI driver; without ``--synthetic``
    this command exits with a clear ``NotImplementedError``-ish message
    so users know to hold until Phase 5.
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
            "Real-cohort training arrives in Phase 5. For now, re-run with "
            "--synthetic to exercise the engine end-to-end."
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


if __name__ == "__main__":  # pragma: no cover
    app()
