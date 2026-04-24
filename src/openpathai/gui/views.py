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

from openpathai.data import DatasetCard, DatasetRegistry, default_registry, list_local
from openpathai.models import ModelCard, ModelRegistry, default_model_registry
from openpathai.safety import CardIssue, validate_card

__all__ = [
    "DatasetsTable",
    "ModelsTable",
    "audit_detail",
    "audit_rows",
    "audit_summary",
    "borderline_badge",
    "cache_summary",
    "cohort_qc_summary",
    "cohort_rows",
    "dataset_train_choices",
    "datasets_rows",
    "device_choices",
    "explainer_choices",
    "local_sources",
    "model_card_snippet",
    "model_issue_summary",
    "models_rows",
    "probability_rows",
    "run_diff_rows",
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


def local_sources() -> frozenset[str]:
    """Return the names of every locally-registered dataset card."""
    return frozenset(c.name for c in list_local())


def datasets_rows(
    registry: DatasetRegistry | None = None,
    *,
    modality: str | None = None,
    tissue: str | None = None,
    tier: str | None = None,
) -> DatasetsTable:
    """Return a list of dataset-row dicts for the Datasets DataFrame.

    When ``registry`` is omitted, a **fresh** :class:`DatasetRegistry` is
    built per call so the GUI always reflects what is on disk — including
    cards the user just registered via the Add-local accordion. Pass an
    explicit registry (or the process-wide :func:`default_registry`) for
    callers that need the cached singleton.
    """
    reg = registry if registry is not None else DatasetRegistry()
    cards = reg.filter(
        modality=modality,  # type: ignore[arg-type]
        tissue=tissue,
        tier=tier,
    )
    local = local_sources()
    rows: DatasetsTable = []
    for card in cards:
        rows.append(_dataset_row(card, source="local" if card.name in local else "shipped"))
    return rows


def _dataset_row(card: DatasetCard, *, source: str) -> dict[str, str]:
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
        "source": source,
    }


def models_rows(
    registry: ModelRegistry | None = None,
    *,
    family: str | None = None,
    framework: str | None = None,
    tier: str | None = None,
    include_invalid: bool = True,
) -> ModelsTable:
    """Return a list of model-row dicts for the Models DataFrame.

    Valid cards are listed first, then contract-failing cards with an
    ``issues`` column describing why they are greyed out in the GUI.
    Pass ``include_invalid=False`` to exclude failures entirely (used by
    the Analyse / Train pickers).
    """
    reg = registry if registry is not None else default_model_registry()
    cards = reg.filter(
        family=family,  # type: ignore[arg-type]
        framework=framework,  # type: ignore[arg-type]
        tier=tier,
    )
    rows: ModelsTable = [_model_row(card, issues=()) for card in cards]
    if include_invalid:
        for invalid_name in reg.invalid_names():
            card = reg.invalid_card(invalid_name)
            if family is not None and card.family != family:
                continue
            if framework is not None and card.source.framework != framework:
                continue
            rows.append(_model_row(card, issues=reg.invalid_issues(invalid_name)))
    return rows


def _model_row(card: ModelCard, *, issues: tuple[CardIssue, ...]) -> dict[str, str]:
    return {
        "name": card.name,
        "display_name": card.display_name,
        "family": card.family,
        "framework": card.source.framework,
        "params_m": f"{card.num_params_m:.1f}",
        "input_size": f"{card.input_size[0]}x{card.input_size[1]}",
        "license": card.source.license,
        "gated": "yes" if card.source.gated else "no",
        "status": "ok" if not issues else "incomplete",
        "issues": model_issue_summary(issues),
    }


def model_issue_summary(issues: tuple[CardIssue, ...]) -> str:
    """Compact comma-separated issue-code string for the Models table."""
    if not issues:
        return ""
    return ", ".join(sorted({i.code for i in issues}))


def model_card_snippet(name: str) -> dict[str, str]:
    """Return key / value pairs the Analyse tab renders under the tile.

    Returns an empty dict when the card is not registered.
    """
    reg = default_model_registry()
    card: ModelCard | None = None
    if reg.has(name):
        card = reg.get(name)
    elif name in reg.invalid_names():
        card = reg.invalid_card(name)
    if card is None:
        return {}
    issues = validate_card(card)
    return {
        "name": card.name,
        "display_name": card.display_name,
        "license": card.source.license,
        "citation": card.citation.text,
        "training_data": card.training_data or "(missing)",
        "intended_use": card.intended_use or "(missing)",
        "out_of_scope_use": card.out_of_scope_use or "(missing)",
        "known_biases": "; ".join(card.known_biases) or "(missing)",
        "status": "ok" if not issues else "incomplete",
        "issues": model_issue_summary(tuple(issues)),
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


def borderline_badge(decision: str, band: str) -> str:
    """Short Markdown badge for the Analyse tab banner.

    ``decision`` is one of ``positive`` / ``negative`` / ``review`` and
    maps to a coloured emoji + capitalised label.
    """
    mapping = {
        "positive": ("🟢", "POSITIVE"),
        "negative": ("🔴", "NEGATIVE"),
        "review": ("🟠", "NEEDS REVIEW"),
    }
    icon, label = mapping.get(decision, ("⚪", decision.upper() or "UNKNOWN"))
    return f"### {icon} {label}  — band `{band}`"


def probability_rows(
    class_names: list[str],
    probabilities: list[float],
) -> list[list[str]]:
    """Shape per-class probabilities for a Gradio DataFrame.

    Returns ``[[class_name, probability_string], ...]`` sorted by
    descending probability.
    """
    paired = sorted(
        zip(class_names, probabilities, strict=False),
        key=lambda kv: kv[1],
        reverse=True,
    )
    return [[name, f"{prob:.4f}"] for name, prob in paired]


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


# --------------------------------------------------------------------------- #
# Audit view-model helpers (Phase 8)
# --------------------------------------------------------------------------- #


def audit_rows(
    *,
    kind: str | None = None,
    since: str | None = None,
    until: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> list[dict[str, str]]:
    """Return a list of row dicts for the Runs tab DataFrame.

    Lazy-imports :mod:`openpathai.safety.audit` so tests that exercise
    other view helpers never pay the SQLite init cost.
    """
    from openpathai.safety.audit import AuditDB

    db = AuditDB.open_default()
    entries = db.list_runs(
        kind=kind,  # type: ignore[arg-type]
        since=since,
        until=until,
        status=status,  # type: ignore[arg-type]
        limit=limit,
    )
    return [
        {
            "run_id": e.run_id,
            "kind": e.kind,
            "mode": e.mode,
            "status": e.status,
            "timestamp_start": e.timestamp_start,
            "timestamp_end": e.timestamp_end or "",
            "tier": e.tier,
            "git_commit": (e.git_commit or "")[:10],
            "pipeline_yaml_hash": (e.pipeline_yaml_hash or "")[:10],
        }
        for e in entries
    ]


def audit_detail(run_id: str) -> dict[str, object]:
    """Return a full row + linked analyses for the detail accordion.

    Empty dict if the run doesn't exist.
    """
    from openpathai.safety.audit import AuditDB

    db = AuditDB.open_default()
    entry = db.get_run(run_id)
    if entry is None:
        return {}
    return {
        "run": entry.model_dump(mode="json"),
        "analyses": [a.model_dump(mode="json") for a in db.list_analyses(run_id=run_id, limit=200)],
    }


def audit_summary() -> dict[str, object]:
    """Return path / size / row counts for the Settings audit sub-section."""
    from openpathai.safety.audit import AuditDB, KeyringTokenStore

    db = AuditDB.open_default()
    stats = db.stats()
    stats["token"] = KeyringTokenStore().status()
    return stats


def run_diff_rows(run_id_a: str, run_id_b: str) -> list[list[str]]:
    """Shape a :class:`RunDiff` into a table-friendly list of rows.

    Returns ``[[field, kind, before, after], ...]``. Empty list when
    either run is missing or the diff is empty.
    """
    from openpathai.safety.audit import AuditDB, diff_runs

    db = AuditDB.open_default()
    a = db.get_run(run_id_a)
    b = db.get_run(run_id_b)
    if a is None or b is None:
        return []
    diff = diff_runs(a, b)
    return [
        [
            d.field,
            d.kind,
            "" if d.before is None else str(d.before),
            "" if d.after is None else str(d.after),
        ]
        for d in diff.deltas
    ]


# --------------------------------------------------------------------------- #
# Cohort view-model helpers (Phase 9)
# --------------------------------------------------------------------------- #


def cohort_rows(yaml_path: str | Path) -> list[dict[str, str]]:
    """Return one row dict per slide in the cohort at ``yaml_path``.

    Empty list when the path doesn't exist or can't be parsed.
    """
    from openpathai.io import Cohort

    if not yaml_path:
        return []
    target = Path(yaml_path).expanduser()
    if not target.is_file():
        return []
    try:
        cohort = Cohort.from_yaml(target)
    except (ValueError, FileNotFoundError):
        return []
    return [
        {
            "slide_id": slide.slide_id,
            "patient_id": slide.patient_id or "",
            "label": slide.label or "",
            "path": slide.path,
            "mpp": "" if slide.mpp is None else f"{slide.mpp:.4f}",
            "magnification": slide.magnification or "",
        }
        for slide in cohort.slides
    ]


def cohort_qc_summary(report) -> dict[str, int]:
    """Passthrough for the Cohorts-tab summary panel."""
    return report.summary() if report is not None else {"pass": 0, "warn": 0, "fail": 0}


def dataset_train_choices() -> list[str]:
    """Return registered dataset names suitable for the Train tab picker."""
    reg = default_registry()
    return list(reg.names())
