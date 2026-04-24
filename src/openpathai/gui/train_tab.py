"""Train tab — synthetic + real-cohort training from the browser.

Phase 6 wired the synthetic path. Phase 9 adds a **Dataset source**
selector (Synthetic / Dataset card / Cohort YAML) so the tab finally
binds to real data. The existing ``LightningTrainer`` accepts either
an ``InMemoryTileBatch`` (synthetic) or a ``torch.utils.data.Dataset``
(dataset card / cohort) — all three paths share the same callback.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openpathai.gui.state import AppState
from openpathai.gui.views import dataset_train_choices, device_choices
from openpathai.models import default_model_registry

SOURCE_SYNTHETIC = "Synthetic (Phase 3 smoke path)"
SOURCE_DATASET = "Dataset card (local)"
SOURCE_COHORT = "Cohort YAML"


def _run_training(  # pragma: no cover - torch-gated
    source: str,
    model_name: str,
    dataset_name: str,
    cohort_path: str,
    class_name_csv: str,
    tile_size: int,
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

    # ------------------------------------------------------------------
    # Build dataset(s) for the selected source.
    # ------------------------------------------------------------------
    train_data: object
    val_data: object | None = None
    selected_num_classes = int(num_classes)
    source_blurb = ""

    if source == SOURCE_SYNTHETIC:
        train_data = synthetic_tile_batch(num_classes=selected_num_classes, seed=int(seed))
        val_data = synthetic_tile_batch(num_classes=selected_num_classes, seed=int(seed) + 1)
        source_blurb = "synthetic"
    elif source == SOURCE_DATASET:
        from openpathai.data import default_registry
        from openpathai.training import build_torch_dataset_from_card

        name = (dataset_name or "").strip()
        if not name:
            return [], "Pick a dataset card name."
        card_registry = default_registry()
        if not card_registry.has(name):
            return [], f"Dataset card {name!r} is not registered."
        dataset_card = card_registry.get(name)
        selected_num_classes = dataset_card.num_classes
        try:
            train_data = build_torch_dataset_from_card(
                dataset_card,
                tile_size=(int(tile_size), int(tile_size)),
            )
        except NotImplementedError as exc:
            return [], f"{exc}"
        source_blurb = f"dataset={dataset_card.name}"
    elif source == SOURCE_COHORT:
        from openpathai.io import Cohort
        from openpathai.training import build_torch_dataset_from_cohort

        path = (cohort_path or "").strip()
        if not path:
            return [], "Provide a cohort YAML path."
        target = Path(path).expanduser()
        if not target.is_file():
            return [], f"Cohort YAML not found: {target}"
        try:
            loaded = Cohort.from_yaml(target)
        except (ValueError, FileNotFoundError) as exc:
            return [], f"Failed to load cohort: {exc}"

        classes_csv = (class_name_csv or "").strip()
        if classes_csv:
            classes = tuple(c.strip() for c in classes_csv.split(",") if c.strip())
        else:
            classes = tuple(sorted({s.label for s in loaded.slides if s.label is not None}))
        if len(classes) < 2:
            return (
                [],
                "Cohort must carry ≥ 2 distinct labels. Either label the "
                "SlideRefs or paste a comma-separated class list above.",
            )
        selected_num_classes = len(classes)
        train_data = build_torch_dataset_from_cohort(
            loaded,
            class_names=classes,
            tile_size=(int(tile_size), int(tile_size)),
        )
        source_blurb = f"cohort={loaded.id}"
    else:
        return [], f"Unknown source: {source!r}"

    config = TrainingConfig(
        model_card=model_name,
        num_classes=selected_num_classes,
        epochs=int(epochs),
        batch_size=int(batch_size),
        seed=int(seed),
        device=device,  # type: ignore[arg-type]
        pretrained=False,
        loss=LossConfig(kind=loss_kind),  # type: ignore[arg-type]
        optimizer=OptimizerConfig(lr=float(lr)),
    )
    trainer = LightningTrainer(config, card=card)
    report = trainer.fit(train=train_data, val=val_data)
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
        f"Finished. source={source_blurb} classes={selected_num_classes} "
        f"final_val_accuracy={report.final_val_accuracy}"
    )

    # Phase 8 audit log — fire-and-forget.
    from openpathai.safety.audit import log_training

    log_training(
        model_id=model_name,
        metrics={
            "source": source_blurb,
            "num_classes": selected_num_classes,
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
            "### Train a tile classifier\n"
            "Pick a **Dataset source** below. Synthetic runs the Phase 3 "
            "smoke path; Dataset card trains on a shipped / locally-registered "
            "card (``method: local`` only in Phase 9); Cohort YAML iterates "
            "the slides in a cohort file."
        )
        source = gr.Radio(
            choices=[SOURCE_SYNTHETIC, SOURCE_DATASET, SOURCE_COHORT],
            value=SOURCE_SYNTHETIC,
            label="Dataset source",
        )
        with gr.Row():
            dataset_name = gr.Dropdown(
                dataset_train_choices(),
                value="kather_crc_5k" if "kather_crc_5k" in dataset_train_choices() else None,
                label="Dataset card name (used only with 'Dataset card')",
            )
            cohort_path = gr.Textbox(
                label="Cohort YAML path (used only with 'Cohort YAML')",
                value="",
            )
            class_name_csv = gr.Textbox(
                label="Class list (optional, comma-separated, cohort mode)",
                value="",
            )
        with gr.Row():
            model = gr.Dropdown(
                default_model_registry().names(),
                value=state.selected_model or "resnet18",
                label="Model card",
            )
            num_classes = gr.Number(value=4, precision=0, label="Number of classes (synthetic)")
            tile_size = gr.Number(value=224, precision=0, label="Tile size")
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
            _run_training,
            inputs=[
                source,
                model,
                dataset_name,
                cohort_path,
                class_name_csv,
                tile_size,
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


__all__ = ["SOURCE_COHORT", "SOURCE_DATASET", "SOURCE_SYNTHETIC", "build"]
