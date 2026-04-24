"""OpenPathAI CLI entry point.

Every subcommand lives in its own module; this file wires them onto the
root Typer app so ``openpathai`` exposes a single, coherent surface.

* Phase 0 — ``hello``, ``--version``.
* Phase 3 — ``models``, ``train``.
* Phase 5 — ``run``, ``analyse``, ``download``, ``datasets``, ``cache``.
* Phase 6 — ``gui``.
* Phase 8 — ``audit``, ``diff``.
* Phase 9 — ``cohort``, ``train --dataset``/``--cohort``.
"""

from __future__ import annotations

from openpathai.cli._app import app
from openpathai.cli.analyse_cmd import register as _register_analyse
from openpathai.cli.audit_cmd import audit_app
from openpathai.cli.cache_cmd import cache_app
from openpathai.cli.cohort_cmd import cohort_app
from openpathai.cli.datasets_cmd import datasets_app
from openpathai.cli.diff_cmd import register as _register_diff
from openpathai.cli.download_cmd import register as _register_download
from openpathai.cli.gui_cmd import register as _register_gui
from openpathai.cli.models_cmd import models_app
from openpathai.cli.run_cmd import register as _register_run
from openpathai.cli.train_cmd import register as _register_train

app.add_typer(models_app)
app.add_typer(datasets_app)
app.add_typer(cache_app)
app.add_typer(audit_app)
app.add_typer(cohort_app)
_register_run(app)
_register_analyse(app)
_register_download(app)
_register_train(app)
_register_gui(app)
_register_diff(app)

__all__ = ["app"]


if __name__ == "__main__":  # pragma: no cover
    app()
