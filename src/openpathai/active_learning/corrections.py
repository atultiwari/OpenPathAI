"""Append-only CSV logger for :class:`LabelCorrection` events.

File format — one header line plus one correction per subsequent row::

    tile_id,predicted_label,corrected_label,annotator_id,iteration,timestamp
    tile-00042,lung_aca,lung_scc,dr-a,0,2026-04-24T13:05:00+00:00
    tile-00173,lung_n,lung_aca,dr-a,0,2026-04-24T13:05:00+00:00

* The header is written exactly once (on the first
  :meth:`~CorrectionLogger.log` call).
* Subsequent opens always append.
* Flushes on every :meth:`~CorrectionLogger.log` call so a crash
  mid-loop still leaves a consistent partial CSV.
* Thread-safe: a per-instance lock serialises writes. For true
  cross-process concurrency, use one logger per process.
"""

from __future__ import annotations

import csv
import threading
from collections.abc import Iterable
from pathlib import Path

from openpathai.active_learning.oracle import LabelCorrection

__all__ = [
    "CORRECTIONS_COLUMNS",
    "CorrectionLogger",
]


CORRECTIONS_COLUMNS: tuple[str, ...] = (
    "tile_id",
    "predicted_label",
    "corrected_label",
    "annotator_id",
    "iteration",
    "timestamp",
)


class CorrectionLogger:
    """Append-only CSV sink. Creates the file + header on first write."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self._lock = threading.Lock()

    def log(self, corrections: Iterable[LabelCorrection]) -> int:
        """Append the given corrections and return the number written."""
        rows = [
            [
                c.tile_id,
                c.predicted_label,
                c.corrected_label,
                c.annotator_id,
                str(c.iteration),
                c.timestamp,
            ]
            for c in corrections
        ]
        if not rows:
            return 0
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            write_header = not self.path.exists() or self.path.stat().st_size == 0
            with self.path.open("a", encoding="utf-8", newline="") as fh:
                writer = csv.writer(fh)
                if write_header:
                    writer.writerow(CORRECTIONS_COLUMNS)
                writer.writerows(rows)
                fh.flush()
        return len(rows)

    def read(self) -> list[dict[str, str]]:
        """Return every logged row as a dict (for tests / notebooks)."""
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))
