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
    "annotate_click_to_segment",
    "annotate_next_tile",
    "annotate_record_correction",
    "annotate_retrain",
    "annotate_session_init",
    "audit_detail",
    "audit_rows",
    "audit_summary",
    "borderline_badge",
    "cache_summary",
    "cohort_qc_summary",
    "cohort_rows",
    "colab_export_for_run",
    "dataset_train_choices",
    "datasets_rows",
    "device_choices",
    "explainer_choices",
    "local_sources",
    "model_card_snippet",
    "model_issue_summary",
    "models_rows",
    "nl_classify_for_gui",
    "nl_draft_pipeline_for_gui",
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

    PHI guard (iron rule #8): we never render the raw ``slide.path``
    in the browser — parent directories can encode patient context
    (``/Users/dr-smith/patient_042/…``). The dataframe shows the
    basename only plus a short stable hash of the parent so two
    slides from the same directory still collate visually.
    """
    from openpathai.io import Cohort
    from openpathai.safety.audit.phi import redact_manifest_path

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
            "path": redact_manifest_path(slide.path),
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


# ─── Phase 16 — Annotate + NL + Pipelines view helpers ─────────────


def annotate_session_init(
    *,
    pool_csv: str | Path,
    out_dir: str | Path,
    annotator_id: str = "dr-a",
    seed_size: int = 12,
    holdout_fraction: float = 0.25,
    random_seed: int = 1234,
) -> dict[str, object]:
    """Set up a new Annotate-tab session from a pool CSV.

    The session state is a plain dict (pydantic-frozen pydantic
    models and Gradio state don't get along) — it carries the
    tile queue, the accumulating correction log, and a resolved
    CSV path for the underlying :class:`CorrectionLogger`.

    No Gradio imports here — the Annotate tab wires Gradio
    widgets around the returned state.
    """
    import csv
    import random

    from openpathai.active_learning import CorrectionLogger, LabelledExample
    from openpathai.active_learning.synthetic import PrototypeTrainer

    pool_path = Path(pool_csv).expanduser()
    if not pool_path.is_file():
        raise FileNotFoundError(f"pool CSV not found at {pool_path}")
    out = Path(out_dir).expanduser()
    out.mkdir(parents=True, exist_ok=True)

    rows: list[tuple[str, str]] = []
    with pool_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames or "tile_id" not in reader.fieldnames:
            raise ValueError(f"pool CSV must have a 'tile_id' column; got {reader.fieldnames!r}")
        if "label" not in reader.fieldnames:
            raise ValueError("pool CSV must have a 'label' column")
        for row in reader:
            tid = (row.get("tile_id") or "").strip()
            lbl = (row.get("label") or "").strip()
            if tid and lbl:
                rows.append((tid, lbl))
    if len(rows) < 4:
        raise ValueError(f"pool CSV {pool_path} has only {len(rows)} usable rows; need >= 4")

    classes = tuple(sorted({r[1] for r in rows}))
    rng = random.Random(random_seed)
    shuffled = list(rows)
    rng.shuffle(shuffled)
    n_holdout = max(1, round(len(shuffled) * holdout_fraction))
    holdout_rows = shuffled[:n_holdout]
    remainder = shuffled[n_holdout:]
    if seed_size >= len(remainder):
        raise ValueError(
            f"seed_size {seed_size} leaves no unlabeled tiles; remainder={len(remainder)}"
        )
    seed_rows = remainder[:seed_size]
    unlabeled_ids = [tid for tid, _ in remainder[seed_size:]]

    # Build a prototype trainer + initial predictions so the UI has
    # something to show on tile 1. This path mirrors the Phase 12
    # CLI exactly.
    from openpathai.cli.active_learn_cmd import _label_signal  # reuse

    signal = _label_signal(rows, classes, dim=16, seed=random_seed)
    trainer = PrototypeTrainer(
        classes=classes,
        embedding_dim=16,
        feature_seed=random_seed,
        label_signal=signal,
    )
    seed_examples = [LabelledExample(tile_id=t, label=lbl) for t, lbl in seed_rows]
    trainer.fit(seed_examples, max_epochs=1, seed=random_seed)

    logger = CorrectionLogger(out / "corrections.csv")
    return {
        "pool_csv": str(pool_path),
        "out_dir": str(out),
        "annotator_id": annotator_id,
        "classes": list(classes),
        "queue": list(unlabeled_ids),
        "cursor": 0,
        "holdout": [{"tile_id": t, "label": lbl} for t, lbl in holdout_rows],
        "seed": [{"tile_id": t, "label": lbl} for t, lbl in seed_rows],
        "oracle_truth": dict(rows),
        "iteration": 0,
        "random_seed": random_seed,
        "log_path": str(logger.path),
        "n_corrections": 0,
    }


def annotate_next_tile(session: dict[str, object]) -> dict[str, object]:
    """Return the current tile id + predicted class for the UI."""
    queue = list(session.get("queue", []))  # type: ignore[arg-type]
    cursor = int(session.get("cursor", 0))  # type: ignore[arg-type]
    if cursor >= len(queue):
        return {
            "tile_id": "",
            "predicted_label": "",
            "class_names": list(session.get("classes", [])),  # type: ignore[arg-type]
            "remaining": 0,
        }
    tile_id = queue[cursor]

    classes = list(session.get("classes", []))  # type: ignore[arg-type]
    trainer = _rehydrate_trainer(session)
    probs = trainer.predict_proba([tile_id])[0]
    predicted = classes[int(probs.argmax())] if classes else ""
    return {
        "tile_id": tile_id,
        "predicted_label": predicted,
        "class_names": classes,
        "remaining": len(queue) - cursor,
    }


def annotate_record_correction(
    session: dict[str, object],
    *,
    tile_id: str,
    corrected_label: str,
) -> dict[str, object]:
    """Append one correction to the CSV log + advance the cursor."""
    from datetime import UTC, datetime

    from openpathai.active_learning import CorrectionLogger, LabelCorrection

    queue = list(session.get("queue", []))  # type: ignore[arg-type]
    cursor = int(session.get("cursor", 0))  # type: ignore[arg-type]
    classes = list(session.get("classes", []))  # type: ignore[arg-type]
    if corrected_label not in classes:
        raise ValueError(f"corrected_label {corrected_label!r} not in classes {classes!r}")
    if cursor >= len(queue):
        return {**session, "status": "queue exhausted"}
    expected = queue[cursor]
    if expected != tile_id:
        raise ValueError(f"tile_id mismatch: queue head is {expected!r}, got {tile_id!r}")

    # Predicted label at the current trainer snapshot.
    trainer = _rehydrate_trainer(session)
    probs = trainer.predict_proba([tile_id])[0]
    predicted_label = classes[int(probs.argmax())] if classes else ""

    correction = LabelCorrection(
        tile_id=tile_id,
        predicted_label=predicted_label or corrected_label,
        corrected_label=corrected_label,
        annotator_id=str(session.get("annotator_id", "dr-a")),
        iteration=int(session.get("iteration", 0)),  # type: ignore[arg-type]
        timestamp=datetime.now(UTC).replace(microsecond=0).isoformat(),
    )
    logger = CorrectionLogger(str(session.get("log_path")))
    logger.log([correction])

    new_session = dict(session)
    new_session["cursor"] = cursor + 1
    new_session["n_corrections"] = int(session.get("n_corrections", 0)) + 1  # type: ignore[arg-type]
    return new_session


def annotate_click_to_segment(image: object, *, point: tuple[int, int]) -> object:
    """MedSAM2 click-to-segment with the Phase-14 fallback."""
    from openpathai.segmentation import (
        default_segmentation_registry,
        resolve_segmenter,
    )

    reg = default_segmentation_registry()
    decision = resolve_segmenter("medsam2", registry=reg)
    adapter = reg.get(decision.resolved_id)
    result = adapter.segment_with_prompt(image, point=point)
    return result.mask.array


def annotate_retrain(session: dict[str, object]) -> dict[str, object]:
    """Run one AL iteration on the accumulated corrections.

    Returns ``{"iteration", "ece_before", "ece_after", "accuracy_after",
    "train_loss"}``. The trainer is rebuilt from session state so each
    retrain is reproducible.
    """
    import csv

    import numpy as np

    from openpathai.active_learning.loop import LabelledExample
    from openpathai.training.metrics import (
        accuracy,
        expected_calibration_error,
    )

    classes = list(session.get("classes", []))  # type: ignore[arg-type]
    class_to_idx = {c: i for i, c in enumerate(classes)}
    seed_rows = list(session.get("seed", []))  # type: ignore[arg-type]
    holdout_rows = list(session.get("holdout", []))  # type: ignore[arg-type]

    labelled: list[LabelledExample] = [
        LabelledExample(tile_id=r["tile_id"], label=r["label"]) for r in seed_rows
    ]
    log_path = Path(str(session.get("log_path")))
    if log_path.exists():
        with log_path.open("r", encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                labelled.append(
                    LabelledExample(
                        tile_id=row["tile_id"],
                        label=row["corrected_label"],
                    )
                )

    trainer = _rehydrate_trainer(session)
    # "Before" metrics on the holdout with the seed-only fit.
    ho_ids = [r["tile_id"] for r in holdout_rows]
    ho_labels = np.asarray([class_to_idx[r["label"]] for r in holdout_rows], dtype=np.int64)
    probs_before = trainer.predict_proba(ho_ids)
    ece_before = float(expected_calibration_error(probs_before, ho_labels))

    # Retrain on seed + corrections.
    seed_int = int(session.get("random_seed", 1234))  # type: ignore[arg-type]
    iteration = int(session.get("iteration", 0)) + 1  # type: ignore[arg-type]
    trainer.fit(labelled, max_epochs=1, seed=seed_int + iteration)
    probs_after = trainer.predict_proba(ho_ids)
    ece_after = float(expected_calibration_error(probs_after, ho_labels))
    acc_after = float(accuracy(ho_labels, probs_after.argmax(axis=1)))

    new_session = dict(session)
    new_session["iteration"] = iteration
    return {
        "session": new_session,
        "iteration": iteration,
        "ece_before": ece_before,
        "ece_after": ece_after,
        "accuracy_after": acc_after,
        "n_labelled": len(labelled),
    }


def nl_classify_for_gui(
    image: object, prompt_csv: str, *, backbone: str = "conch"
) -> list[tuple[str, float]]:
    """Thin wrapper around :func:`openpathai.nl.classify_zero_shot`
    for the Analyse-tab accordion. Returns ``[(prompt, prob), …]``
    ordered by probability for the Gradio bar chart."""
    import numpy as np

    from openpathai.nl import classify_zero_shot

    prompts = [p.strip() for p in prompt_csv.split(",") if p.strip()]
    if len(prompts) < 2:
        raise ValueError(
            "enter at least two comma-separated prompts (zero-shot softmax needs a partition)"
        )
    result = classify_zero_shot(np.asarray(image), prompts=prompts, backbone_id=backbone)
    return sorted(
        zip(result.prompts, result.probs, strict=True),
        key=lambda row: -row[1],
    )


def nl_draft_pipeline_for_gui(prompt: str) -> dict[str, object]:
    """Wrapper for the Pipelines-tab chat accordion.

    Returns a dict carrying either the drafted YAML text + pipeline
    id or an ``error`` key with the actionable message (LLM
    unavailable / parse failure). Never raises — the GUI callback
    is expected to render either shape.
    """
    from openpathai.cli.pipeline_yaml import dump_pipeline
    from openpathai.nl import (
        LLMUnavailableError,
        default_llm_backend_registry,
        detect_default_backend,
        draft_pipeline_from_prompt,
    )
    from openpathai.nl.pipeline_gen import PipelineDraftError

    if not prompt.strip():
        return {"error": "prompt must be non-empty"}
    try:
        backend = detect_default_backend(registry=default_llm_backend_registry())
    except LLMUnavailableError as exc:
        return {"error": str(exc)}
    try:
        draft = draft_pipeline_from_prompt(prompt, backend=backend)
    except PipelineDraftError as exc:
        return {
            "error": (
                f"LLM produced invalid YAML after 3 attempts: {exc!s}\n"
                "Last output:\n" + (exc.last_output or "(empty)")
            )
        }
    return {
        "pipeline_id": draft.pipeline.id,
        "backend_id": draft.backend_id,
        "model_id": draft.model_id,
        "attempts": draft.attempts,
        "yaml_text": dump_pipeline(draft.pipeline),
    }


def _rehydrate_trainer(session: dict[str, object]):
    """Build a fresh :class:`PrototypeTrainer` from session state."""
    from openpathai.active_learning.synthetic import PrototypeTrainer
    from openpathai.cli.active_learn_cmd import _label_signal

    classes = tuple(session.get("classes", []))  # type: ignore[arg-type]
    rows = [(tid, lbl) for tid, lbl in session.get("oracle_truth", {}).items()]  # type: ignore[union-attr]
    seed = int(session.get("random_seed", 1234))  # type: ignore[arg-type]
    signal = _label_signal(rows, classes, dim=16, seed=seed)
    trainer = PrototypeTrainer(
        classes=classes,
        embedding_dim=16,
        feature_seed=seed,
        label_signal=signal,
    )
    # Refit on the current labelled set so predictions reflect the
    # latest state. Labelled = seed + every correction logged so far.
    from openpathai.active_learning.loop import LabelledExample

    labelled = [
        LabelledExample(tile_id=r["tile_id"], label=r["label"])
        for r in session.get("seed", [])  # type: ignore[arg-type]
    ]
    log_path = Path(str(session.get("log_path", "")))
    if log_path.exists():
        import csv

        with log_path.open("r", encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                labelled.append(
                    LabelledExample(
                        tile_id=row["tile_id"],
                        label=row["corrected_label"],
                    )
                )
    trainer.fit(labelled, max_epochs=1, seed=seed)
    return trainer


def colab_export_for_run(
    run_id: str,
    pipeline_yaml_path: str,
    *,
    out_dir: str | Path | None = None,
) -> tuple[str | None, str]:
    """Render a Colab notebook for ``run_id`` + a pipeline YAML.

    Returns ``(output_path_or_None, status_message)``. Used by the
    Phase 11 **Export for Colab** accordion on the Runs tab. Keeps
    the GUI module gradio-agnostic.
    """
    import tempfile

    from openpathai.cli.pipeline_yaml import PipelineYamlError, load_pipeline
    from openpathai.export import ColabExportError, render_notebook, write_notebook
    from openpathai.safety.audit import AuditDB

    run_id = (run_id or "").strip()
    yaml_text = (pipeline_yaml_path or "").strip()
    if not yaml_text:
        return None, "Enter the pipeline YAML path used for this run."

    yaml_path = Path(yaml_text).expanduser()
    if not yaml_path.is_file():
        return None, f"Pipeline YAML not found at {yaml_path}."

    try:
        pipeline = load_pipeline(yaml_path)
    except PipelineYamlError as exc:
        return None, f"Pipeline YAML rejected: {exc}"

    audit_entry = None
    if run_id:
        db = AuditDB.open_default()
        audit_entry = db.get_run(run_id)
        if audit_entry is None:
            return None, (
                f"No audit run {run_id!r} — proceeding without lineage. "
                "Clear the run-id field to silence this warning."
            )

    try:
        notebook = render_notebook(pipeline=pipeline, audit_entry=audit_entry)
    except ColabExportError as exc:
        return None, f"Export failed: {exc}"

    target_dir = Path(out_dir) if out_dir else Path(tempfile.mkdtemp(prefix="openpathai_colab_"))
    target_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"_{run_id}" if run_id else ""
    out_path = write_notebook(notebook, target_dir / f"{pipeline.id}{suffix}.ipynb")
    return str(out_path), f"Wrote notebook → {out_path}"
