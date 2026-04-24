"""Oracle abstraction + CSV-backed simulated oracle (Phase 12).

In the CLI prototype, the "oracle" is a CSV the researcher exports
from ground-truth labels. Phase 16 will swap this for a real UI where
a pathologist corrects labels interactively — the
:class:`Oracle` protocol lets both paths coexist.

PHI guardrail: the CSV is read with **two named columns only**
(``tile_id``, ``label``). No extra columns ever reach
:class:`LabelCorrection` or the audit layer downstream.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "CSVOracle",
    "LabelCorrection",
    "Oracle",
    "OracleError",
]


class OracleError(RuntimeError):
    """Raised when an oracle cannot answer a query (missing tile,
    malformed CSV, etc.)."""


class LabelCorrection(BaseModel):
    """One annotator correction event."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tile_id: str = Field(min_length=1)
    predicted_label: str
    corrected_label: str
    annotator_id: str = Field(min_length=1)
    iteration: int = Field(ge=0)
    timestamp: str = Field(min_length=1)


class Oracle(Protocol):
    """Labels tiles on request. Implementations must be pure — i.e.
    calling :meth:`query` twice with the same arguments returns
    equivalent corrections."""

    annotator_id: str

    def query(
        self,
        tile_ids: Sequence[str],
        *,
        predictions: Mapping[str, str],
        iteration: int,
    ) -> list[LabelCorrection]: ...


def _utcnow_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


class CSVOracle:
    """Ground-truth oracle backed by a CSV with columns
    ``tile_id,label``.

    The CSV is loaded **once** at construction and held in memory
    (small — the LC25000 smoke subset is a few hundred rows). Any
    additional columns are silently ignored to avoid PHI leakage.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        id_column: str = "tile_id",
        label_column: str = "label",
        annotator_id: str = "simulated-oracle",
    ) -> None:
        self.path = Path(path).expanduser().resolve()
        self.annotator_id = annotator_id
        self._id_column = id_column
        self._label_column = label_column
        self._labels: dict[str, str] = self._load()

    def _load(self) -> dict[str, str]:
        if not self.path.exists():
            raise OracleError(f"oracle CSV not found: {self.path}")
        labels: dict[str, str] = {}
        with self.path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None or self._id_column not in reader.fieldnames:
                raise OracleError(
                    f"oracle CSV must contain column {self._id_column!r}; "
                    f"got columns {reader.fieldnames!r}"
                )
            if self._label_column not in reader.fieldnames:
                raise OracleError(
                    f"oracle CSV must contain column {self._label_column!r}; "
                    f"got columns {reader.fieldnames!r}"
                )
            for row in reader:
                tile_id = (row.get(self._id_column) or "").strip()
                label = (row.get(self._label_column) or "").strip()
                if not tile_id or not label:
                    continue
                labels[tile_id] = label
        if not labels:
            raise OracleError(f"oracle CSV {self.path} contained no rows")
        return labels

    def query(
        self,
        tile_ids: Sequence[str],
        *,
        predictions: Mapping[str, str],
        iteration: int,
    ) -> list[LabelCorrection]:
        """Return one :class:`LabelCorrection` per requested
        ``tile_id``, using the CSV-loaded ground truth as the
        corrected label.

        Raises :class:`OracleError` if any ``tile_id`` is missing
        from the CSV.
        """
        missing = [tid for tid in tile_ids if tid not in self._labels]
        if missing:
            raise OracleError(
                f"oracle has no label for {len(missing)} tile(s): "
                f"{missing[:3]}{'…' if len(missing) > 3 else ''}"
            )
        timestamp = _utcnow_iso()
        return [
            LabelCorrection(
                tile_id=tid,
                predicted_label=predictions.get(tid, ""),
                corrected_label=self._labels[tid],
                annotator_id=self.annotator_id,
                iteration=iteration,
                timestamp=timestamp,
            )
            for tid in tile_ids
        ]

    @property
    def tile_ids(self) -> tuple[str, ...]:
        return tuple(self._labels.keys())

    def label_of(self, tile_id: str) -> str:
        try:
            return self._labels[tile_id]
        except KeyError as exc:
            raise OracleError(f"oracle has no label for tile {tile_id!r}") from exc

    def known_labels(self) -> frozenset[str]:
        return frozenset(self._labels.values())

    def __len__(self) -> int:
        return len(self._labels)

    def __contains__(self, tile_id: object) -> bool:
        return isinstance(tile_id, str) and tile_id in self._labels


def build_oracle_for_tests(
    labels: Iterable[tuple[str, str]],
    *,
    annotator_id: str = "simulated-oracle",
    tmp_path: Path,
) -> CSVOracle:
    """Write a two-column CSV to ``tmp_path/oracle.csv`` and return a
    loaded :class:`CSVOracle`. Tests reuse this helper.
    """
    target = tmp_path / "oracle.csv"
    with target.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["tile_id", "label"])
        for tile_id, label in labels:
            writer.writerow([tile_id, label])
    return CSVOracle(target, annotator_id=annotator_id)
