"""Train tab — drive the Phase 3 supervised trainer from the browser.

Phase 6 wires the synthetic tile path so users can exercise the engine
without downloading anything. Real-cohort training slots in with the
Phase 9 cohort driver.
"""

from __future__ import annotations

from typing import Any

from openpathai.gui.state import AppState
from openpathai.gui.views import device_choices
from openpathai.models import default_model_registry


def _run_synthetic_training(  # pragma: no cover - torch-gated
    model_name: str,
    num_classes: int,
    epochs: int,
    batch_size: int,
    lr: float,
    loss_kind: str,
    seed: int,
    device: str,
):
    import importlib.util

    if importlib.util.find_spec("torch") is None:
        return [], "Install the `[train]` extra (torch + timm) to run training."

    from openpathai.training import (
        LossConfig,
        OptimizerConfig,
        TrainingConfig,
        synthetic_tile_batch,
    )
    from openpathai.training.engine import LightningTrainer

    registry = default_model_registry()
    if not registry.has(model_name):
        return [], f"Model card {model_name!r} is not registered."
    card = registry.get(model_name)

    config = TrainingConfig(
        model_card=model_name,
        num_classes=int(num_classes),
        epochs=int(epochs),
        batch_size=int(batch_size),
        seed=int(seed),
        device=device,  # type: ignore[arg-type]
        pretrained=False,
        loss=LossConfig(kind=loss_kind),  # type: ignore[arg-type]
        optimizer=OptimizerConfig(lr=float(lr)),
    )
    train_batch = synthetic_tile_batch(num_classes=int(num_classes), seed=int(seed))
    val_batch = synthetic_tile_batch(num_classes=int(num_classes), seed=int(seed) + 1)
    trainer = LightningTrainer(config, card=card)
    report = trainer.fit(train=train_batch, val=val_batch)
    rows = [
        [
            rec.epoch,
            rec.train_loss,
            rec.val_loss,
            rec.val_accuracy,
            rec.val_macro_f1,
            rec.val_ece,
        ]
        for rec in report.history
    ]
    status = (
        f"Finished. Final val acc={report.final_val_accuracy} "
        f"ECE before={report.ece_before_calibration} "
        f"ECE after={report.ece_after_calibration}"
    )

    # Phase 8 audit log — fire-and-forget; never raises.
    from openpathai.safety.audit import log_training

    log_training(
        model_id=model_name,
        metrics={
            "num_classes": int(num_classes),
            "epochs": int(epochs),
            "batch_size": int(batch_size),
            "loss": loss_kind,
            "lr": float(lr),
            "seed": int(seed),
            "final_val_accuracy": report.final_val_accuracy,
            "ece_before_calibration": report.ece_before_calibration,
            "ece_after_calibration": report.ece_after_calibration,
        },
    )

    return rows, status


def build(state: AppState) -> Any:  # pragma: no cover - gradio-gated renderer
    import gradio as gr

    with gr.Blocks() as tab:
        gr.Markdown(
            "### Train (synthetic smoke path)\n"
            "Trains a tile classifier on the Phase 3 synthetic batch. "
            "Real-cohort training plugs in with the Phase 9 cohort driver."
        )
        with gr.Row():
            model = gr.Dropdown(
                default_model_registry().names(),
                value=state.selected_model or "resnet18",
                label="Model card",
            )
            num_classes = gr.Number(value=4, precision=0, label="Number of classes")
            epochs = gr.Number(value=1, precision=0, label="Epochs")
            batch_size = gr.Number(value=8, precision=0, label="Batch size")
        with gr.Row():
            lr = gr.Number(value=1e-2, label="Learning rate")
            loss_kind = gr.Dropdown(
                ["cross_entropy", "weighted_cross_entropy", "focal", "ldam"],
                value="cross_entropy",
                label="Loss kind",
            )
            seed = gr.Number(value=0, precision=0, label="Seed")
            device = gr.Dropdown(device_choices(), value=state.device, label="Device")
        start = gr.Button("Start training")
        status = gr.Markdown("")
        table = gr.Dataframe(
            headers=[
                "epoch",
                "train_loss",
                "val_loss",
                "val_accuracy",
                "val_macro_f1",
                "val_ece",
            ],
            interactive=False,
        )
        start.click(
            _run_synthetic_training,
            inputs=[
                model,
                num_classes,
                epochs,
                batch_size,
                lr,
                loss_kind,
                seed,
                device,
            ],
            outputs=[table, status],
        )
    return tab


__all__ = ["build"]
