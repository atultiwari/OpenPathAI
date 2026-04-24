"""Opt-in MLflow sink — mirrors Phase 8 audit rows into MLflow.

Activation
----------
``OPENPATHAI_MLFLOW_ENABLED=1`` flips the sink on. With the flag
unset (default) the sink returns a no-op object, so importing this
module is cheap and ``mlflow`` is **never** imported.

Tracking URI
------------
Defaults to ``file://$OPENPATHAI_HOME/mlruns``. Override via the
standard ``MLFLOW_TRACKING_URI`` environment variable.

Contract
--------
Every sink method wraps the mlflow call in ``try/except`` and logs a
warning on failure — the iron rule from Phase 8 (*audit failure must
not break a real run*) extends to this secondary sink.

The Phase 8 audit DB remains the single source of truth. MLflow is
strictly additional: a nicer UI for metrics + an API for remote
dashboards in Phase 18. A corrupt / missing MLflow store is tolerated
silently.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - type-only
    from openpathai.safety.audit import AnalysisEntry, AuditEntry

__all__ = [
    "MLflowSink",
    "default_mlflow_uri",
    "mlflow_enabled",
]


_LOGGER = logging.getLogger(__name__)


def mlflow_enabled() -> bool:
    """Whether the sink should actually log."""
    value = os.environ.get("OPENPATHAI_MLFLOW_ENABLED", "0").strip().lower()
    return value in {"1", "true", "yes", "on"}


def default_mlflow_uri() -> str:
    """Honours ``MLFLOW_TRACKING_URI`` first; otherwise
    ``file://$OPENPATHAI_HOME/mlruns``.
    """
    existing = os.environ.get("MLFLOW_TRACKING_URI", "").strip()
    if existing:
        return existing
    root = Path(os.environ.get("OPENPATHAI_HOME", Path.home() / ".openpathai"))
    return f"file://{(root / 'mlruns').resolve()}"


class MLflowSink:
    """Secondary sink behind :mod:`openpathai.safety.audit.hooks`.

    The constructor is free — no import, no IO. The first
    ``log_*`` call lazy-imports mlflow and configures the tracking URI.
    If mlflow is not installed (or any step fails) the sink logs a
    warning and returns, leaving the primary audit DB write intact.
    """

    def __init__(self, tracking_uri: str | None = None) -> None:
        self._tracking_uri = tracking_uri
        self._configured = False
        self._mlflow: Any | None = None

    # ------------------------------------------------------------------
    # Lazy configuration
    # ------------------------------------------------------------------

    def _ensure_mlflow(self) -> Any | None:
        if self._mlflow is not None:
            return self._mlflow
        try:
            import mlflow  # type: ignore[import-not-found]
        except ImportError:
            _LOGGER.warning(
                "MLflow sink enabled but the `mlflow` package is not installed; "
                "run `uv sync --extra mlflow` to install it."
            )
            return None
        if not self._configured:
            mlflow.set_tracking_uri(self._tracking_uri or default_mlflow_uri())
            self._configured = True
        self._mlflow = mlflow
        return mlflow

    @staticmethod
    def _safe_experiment(mlflow: Any, name: str) -> str | None:
        """Create / lookup an experiment; return its id or None on failure."""
        try:
            experiment = mlflow.get_experiment_by_name(name)
            if experiment is not None:
                return experiment.experiment_id
            return mlflow.create_experiment(name)
        except Exception as exc:
            _LOGGER.warning("MLflow sink: cannot resolve experiment %r: %s", name, exc)
            return None

    # ------------------------------------------------------------------
    # Public sink methods
    # ------------------------------------------------------------------

    def log_pipeline(
        self,
        entry: AuditEntry,
        *,
        manifest_path: str | None = None,
    ) -> str | None:
        """Log a pipeline run. Returns the mlflow run id or ``None``."""
        return self._log_run(
            kind="pipeline",
            entry=entry,
            extra_artifact_path=manifest_path,
        )

    def log_training(
        self,
        entry: AuditEntry,
        *,
        report_path: str | None = None,
    ) -> str | None:
        """Log a training run. Returns the mlflow run id or ``None``."""
        return self._log_run(
            kind="training",
            entry=entry,
            extra_artifact_path=report_path,
        )

    def log_analysis(
        self,
        entry: AnalysisEntry,
        *,
        pdf_path: str | None = None,
    ) -> str | None:
        """Log a single analysis row."""
        mlflow = self._ensure_mlflow()
        if mlflow is None:
            return None
        try:
            experiment_id = self._safe_experiment(mlflow, "openpathai.analyses")
            if experiment_id is None:
                return None
            with mlflow.start_run(
                experiment_id=experiment_id,
                run_name=entry.analysis_id,
            ) as run:
                mlflow.log_params(
                    {
                        "analysis_id": entry.analysis_id,
                        "run_id": entry.run_id or "",
                        "model_id": entry.model_id,
                        "mode": entry.mode,
                        "prediction": entry.prediction,
                        "decision": entry.decision,
                        "band": entry.band,
                    }
                )
                mlflow.log_metric("confidence", float(entry.confidence))
                if pdf_path and Path(pdf_path).is_file():
                    mlflow.log_artifact(pdf_path)
                return run.info.run_id
        except Exception as exc:
            _LOGGER.warning("MLflow sink log_analysis failed (non-fatal): %s", exc)
            return None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _log_run(
        self,
        *,
        kind: str,
        entry: AuditEntry,
        extra_artifact_path: str | None,
    ) -> str | None:
        mlflow = self._ensure_mlflow()
        if mlflow is None:
            return None
        try:
            experiment_name = f"openpathai.{kind}"
            experiment_id = self._safe_experiment(mlflow, experiment_name)
            if experiment_id is None:
                return None
            with mlflow.start_run(
                experiment_id=experiment_id,
                run_name=entry.run_id,
            ) as run:
                mlflow.log_params(
                    {
                        "run_id": entry.run_id,
                        "kind": entry.kind,
                        "mode": entry.mode,
                        "status": entry.status,
                        "tier": entry.tier,
                        "pipeline_yaml_hash": entry.pipeline_yaml_hash,
                        "graph_hash": entry.graph_hash,
                        "git_commit": entry.git_commit,
                    }
                )
                if entry.metrics_json:
                    try:
                        metrics = json.loads(entry.metrics_json)
                    except json.JSONDecodeError:
                        metrics = {}
                    for name, value in metrics.items():
                        if isinstance(value, (int, float)):
                            try:
                                mlflow.log_metric(str(name), float(value))
                            except Exception:
                                continue
                        else:
                            mlflow.log_param(f"metric.{name}", str(value)[:250])
                if extra_artifact_path and Path(extra_artifact_path).is_file():
                    mlflow.log_artifact(extra_artifact_path)
                return run.info.run_id
        except Exception as exc:
            _LOGGER.warning("MLflow sink log_%s failed (non-fatal): %s", kind, exc)
            return None


# Singleton — instantiated lazily so nothing imports mlflow on startup.
_default_sink: MLflowSink | None = None


def _sink() -> MLflowSink | None:
    """Return the process-wide sink or ``None`` when disabled."""
    if not mlflow_enabled():
        return None
    global _default_sink
    if _default_sink is None:
        _default_sink = MLflowSink()
    return _default_sink
