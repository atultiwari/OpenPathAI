"""OpenPathAI CLI entry point.

Every subcommand lives in its own module; this file wires them onto the
root Typer app so ``openpathai`` exposes a single, coherent surface.

* Phase 0 — ``hello``, ``--version``.
* Phase 3 — ``models``, ``train``.
* Phase 5 — ``run``, ``analyse``, ``download``, ``datasets``, ``cache``.
* Phase 6 — ``gui``.
* Phase 8 — ``audit``, ``diff``.
* Phase 9 — ``cohort``, ``train --dataset``/``--cohort``.
* Phase 10 — ``run --workers / --parallel-mode / --snakefile``, ``mlflow-ui``.
* Phase 11 — ``export-colab``, ``sync``.
* Phase 12 — ``active-learn``.
* Phase 13 — ``foundation``, ``mil``, ``linear-probe``.
* Phase 14 — ``detection``, ``segmentation``.
* Phase 15 — ``llm``, ``nl``.
* Phase 17 — ``manifest``, ``methods``.
* Phase 19 — ``serve`` (FastAPI backend for the v2.0 React canvas).
"""

from __future__ import annotations

from openpathai.cli._app import app
from openpathai.cli.active_learn_cmd import register as _register_active_learn
from openpathai.cli.analyse_cmd import register as _register_analyse
from openpathai.cli.audit_cmd import audit_app
from openpathai.cli.cache_cmd import cache_app
from openpathai.cli.cohort_cmd import cohort_app
from openpathai.cli.datasets_cmd import datasets_app
from openpathai.cli.detection_cmd import detection_app
from openpathai.cli.diff_cmd import register as _register_diff
from openpathai.cli.download_cmd import register as _register_download
from openpathai.cli.export_cmd import register as _register_export
from openpathai.cli.foundation_cmd import foundation_app
from openpathai.cli.gui_cmd import register as _register_gui
from openpathai.cli.linear_probe_cmd import register as _register_linear_probe
from openpathai.cli.llm_cmd import llm_app
from openpathai.cli.manifest_cmd import manifest_app
from openpathai.cli.methods_cmd import methods_app
from openpathai.cli.mil_cmd import mil_app
from openpathai.cli.mlflow_cmd import register as _register_mlflow
from openpathai.cli.models_cmd import models_app
from openpathai.cli.nl_cmd import nl_app
from openpathai.cli.run_cmd import register as _register_run
from openpathai.cli.segmentation_cmd import segmentation_app
from openpathai.cli.serve_cmd import register as _register_serve
from openpathai.cli.train_cmd import register as _register_train

app.add_typer(models_app)
app.add_typer(datasets_app)
app.add_typer(cache_app)
app.add_typer(audit_app)
app.add_typer(cohort_app)
app.add_typer(foundation_app)
app.add_typer(mil_app)
app.add_typer(detection_app)
app.add_typer(segmentation_app)
app.add_typer(llm_app)
app.add_typer(nl_app)
app.add_typer(manifest_app)
app.add_typer(methods_app)
_register_run(app)
_register_analyse(app)
_register_download(app)
_register_train(app)
_register_gui(app)
_register_diff(app)
_register_mlflow(app)
_register_export(app)
_register_active_learn(app)
_register_linear_probe(app)
_register_serve(app)

__all__ = ["app"]


if __name__ == "__main__":  # pragma: no cover
    app()
