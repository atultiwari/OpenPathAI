"""``openpathai linear-probe`` — fit a linear probe on pre-extracted features.

Input: a ``.npz`` bundle with keys ``features_train`` /
``labels_train`` / ``features_val`` / ``labels_val`` / ``class_names``.
This shape keeps the CLI torch-free — users or upstream nodes
(Phase 3+) extract the features; this command just fits the probe
and emits a report.

For a full end-to-end run (backbone → features → probe) see the
reference pipeline ``pipelines/foundation_linear_probe.yaml``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import numpy as np
import typer

from openpathai.foundation import default_foundation_registry, resolve_backbone
from openpathai.training.linear_probe import LinearProbeConfig, fit_linear_probe

__all__ = ["register"]


def register(app: typer.Typer) -> None:
    @app.command("linear-probe")
    def linear_probe(
        features: Annotated[
            Path,
            typer.Option(
                "--features",
                help=(
                    "Path to a .npz bundle with ``features_train`` + "
                    "``labels_train`` + optional ``features_val`` / "
                    "``labels_val`` + ``class_names`` (object array of str)."
                ),
            ),
        ],
        backbone: Annotated[
            str,
            typer.Option(
                "--backbone",
                help=(
                    "Foundation backbone id the features came from. "
                    "Resolved via the fallback resolver so the emitted "
                    "report records requested vs actually-used model."
                ),
            ),
        ] = "dinov2_vits14",
        out: Annotated[
            Path | None,
            typer.Option(
                "--out",
                help="Optional path to write the LinearProbeReport JSON.",
            ),
        ] = None,
        seed: Annotated[
            int,
            typer.Option("--seed", min=0, help="Deterministic random seed."),
        ] = 1234,
        strict: Annotated[
            bool,
            typer.Option(
                "--strict-backbone",
                help="Disable backbone fallback (hard-fail on gated access).",
            ),
        ] = False,
        no_audit: Annotated[
            bool,
            typer.Option(
                "--no-audit",
                help="Skip writing an audit row for this run.",
            ),
        ] = False,
    ) -> None:
        """Fit a linear probe on pre-extracted foundation features."""
        if not features.exists():
            typer.secho(f"features file not found: {features}", fg="red", err=True)
            raise typer.Exit(code=2)
        bundle = np.load(features, allow_pickle=True)
        required = ("features_train", "labels_train", "class_names")
        for key in required:
            if key not in bundle:
                typer.secho(
                    f"features bundle missing required key {key!r}; got {list(bundle)}",
                    fg="red",
                    err=True,
                )
                raise typer.Exit(code=2)
        features_train = np.asarray(bundle["features_train"], dtype=np.float32)
        labels_train = np.asarray(bundle["labels_train"], dtype=np.int64)
        class_names = tuple(str(c) for c in np.atleast_1d(bundle["class_names"]))
        features_val = (
            np.asarray(bundle["features_val"], dtype=np.float32)
            if "features_val" in bundle
            else None
        )
        labels_val = (
            np.asarray(bundle["labels_val"], dtype=np.int64) if "labels_val" in bundle else None
        )

        reg = default_foundation_registry()
        try:
            decision = resolve_backbone(backbone, registry=reg, allow_fallback=not strict)
        except ValueError as exc:
            typer.secho(str(exc), fg="red", err=True)
            raise typer.Exit(code=2) from exc

        report = fit_linear_probe(
            features_train,
            labels_train,
            num_classes=len(class_names),
            class_names=class_names,
            backbone_id=decision.requested_id,
            resolved_backbone_id=decision.resolved_id,
            fallback_reason=decision.reason,
            features_val=features_val,
            labels_val=labels_val,
            config=LinearProbeConfig(random_seed=seed),
        )

        if out is not None:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(report.model_dump_json(indent=2), encoding="utf-8")

        if not no_audit:
            try:
                from openpathai.safety.audit import AuditDB

                audit_db = AuditDB.open_default()
                audit_db.insert_run(
                    kind="training",
                    mode="exploratory",
                    status="success",
                    tier="local",
                    metrics={
                        "linear_probe": True,
                        "backbone_id": decision.requested_id,
                        "resolved_backbone_id": decision.resolved_id,
                        "fallback_reason": decision.reason,
                        "accuracy": report.accuracy,
                        "macro_f1": report.macro_f1,
                        "ece_before": report.ece_before,
                        "ece_after": report.ece_after,
                    },
                )
            except Exception as exc:  # pragma: no cover — audit is best-effort
                typer.secho(f"(audit log skipped: {exc!s})", fg="yellow", err=True)

        typer.echo(json.dumps(report.model_dump(), indent=2, sort_keys=True))
