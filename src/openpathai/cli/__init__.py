"""Command-line interface for OpenPathAI.

The CLI is intentionally thin: every sub-command is a shallow wrapper over a
library function. See ``docs/planning/master-plan.md`` §4 ("library-first,
UI-last").
"""

from __future__ import annotations

from openpathai.cli.main import app

__all__ = ["app"]
