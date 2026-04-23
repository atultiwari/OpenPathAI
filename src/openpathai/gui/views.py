"""Pure-Python view-model helpers feeding the Gradio tabs.

Keeping the data-shaping code out of the tab modules means:

* tests can verify row shapes without importing gradio,
* the same helpers can drive a future React canvas (Phase 20) or the
  auto-Methods generator (Phase 17),
* tab modules stay tiny and focused on widget wiring.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

from openpathai.data import DatasetCard, DatasetRegistry, default_registry
from openpathai.models import ModelCard, ModelRegistry, default_model_registry

__all__ = [
    "DatasetsTable",
    "ModelsTable",
    "cache_summary",
    "datasets_rows",
    "device_choices",
    "explainer_choices",
    "models_rows",
    "target_layer_hint",
]


# ``(name, family/modality, size_blurb, gated, licence, notes)`` style.
DatasetsTable = list[dict[str, str]]
ModelsTable = list[dict[str, str]]


def _size_blurb(size_gb: float | None) -> str:
    """Consistent size label used in the Datasets tab."""
    if size_gb is None:
        return "?"
    if size_gb >= 100:
        return f"{size_gb:.0f} GB"
    if size_gb >= 1.0:
        return f"{size_gb:.1f} GB"
    return f"{size_gb * 1024:.0f} MB"


def datasets_rows(
    registry: DatasetRegistry | None = None,
    *,
    modality: str | None = None,
    tissue: str | None = None,
    tier: str | None = None,
) -> DatasetsTable:
    """Return a list of dataset-row dicts for the Datasets DataFrame."""
    reg = registry if registry is not None else default_registry()
    cards = reg.filter(
        modality=modality,  # type: ignore[arg-type]
        tissue=tissue,
        tier=tier,
    )
    rows: DatasetsTable = []
    for card in cards:
        rows.append(_dataset_row(card))
    return rows


def _dataset_row(card: DatasetCard) -> dict[str, str]:
    d = card.download
    return {
        "name": card.name,
        "display_name": card.display_name,
        "modality": card.modality,
        "tissue": ", ".join(card.tissue),
        "classes": str(card.num_classes),
        "size": _size_blurb(d.size_gb),
        "gated": "yes" if d.gated else "no",
        "confirm": "yes" if d.should_confirm_before_download else "no",
        "license": card.license,
    }


def models_rows(
    registry: ModelRegistry | None = None,
    *,
    family: str | None = None,
    framework: str | None = None,
    tier: str | None = None,
) -> ModelsTable:
    """Return a list of model-row dicts for the Models DataFrame."""
    reg = registry if registry is not None else default_model_registry()
    cards = reg.filter(
        family=family,  # type: ignore[arg-type]
        framework=framework,  # type: ignore[arg-type]
        tier=tier,
    )
    rows: ModelsTable = []
    for card in cards:
        rows.append(_model_row(card))
    return rows


def _model_row(card: ModelCard) -> dict[str, str]:
    return {
        "name": card.name,
        "display_name": card.display_name,
        "family": card.family,
        "framework": card.source.framework,
        "params_m": f"{card.num_params_m:.1f}",
        "input_size": f"{card.input_size[0]}x{card.input_size[1]}",
        "license": card.source.license,
        "gated": "yes" if card.source.gated else "no",
    }


def cache_summary(cache_root: Path | None = None) -> dict[str, str]:
    """Return a cache-root / entry-count / size summary for the
    Settings tab. Pure Python; reused by the CLI in Phase 5."""
    root = cache_root if cache_root is not None else Path.home() / ".openpathai" / "cache"
    entries = 0
    total = 0
    if root.is_dir():
        for child in root.iterdir():
            if child.is_dir():
                entries += 1
                for sub in child.rglob("*"):
                    if sub.is_file():
                        with contextlib.suppress(OSError):
                            total += sub.stat().st_size
    return {
        "cache_root": str(root),
        "entries": str(entries),
        "total_size_mib": f"{total / (1024 * 1024):.2f}",
    }


def explainer_choices() -> list[str]:
    """Ordered list of explainers exposed in the Analyse tab."""
    return [
        "gradcam",
        "gradcam_plus_plus",
        "eigencam",
        "integrated_gradients",
        "attention_rollout",
    ]


def device_choices() -> list[str]:
    """Ordered list of device options shown in the Analyse + Train tabs."""
    return ["auto", "cpu", "cuda", "mps"]


def target_layer_hint(model_name: str | None) -> str:
    """Best-guess target-layer suggestion for the Analyse tab."""
    if model_name is None:
        return ""
    if model_name.startswith("resnet"):
        return "layer4"
    if model_name.startswith("efficientnet"):
        return "blocks"
    if model_name.startswith("mobilenet"):
        return "blocks"
    if model_name.startswith("convnext"):
        return "stages"
    if model_name.startswith("vit"):
        return "blocks"
    if model_name.startswith("swin"):
        return "layers"
    return ""
