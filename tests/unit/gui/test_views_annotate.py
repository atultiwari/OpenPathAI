"""Phase 16 — Annotate view-model helpers."""

from __future__ import annotations

import csv
import random
from pathlib import Path

import numpy as np
import pytest

from openpathai.gui.views import (
    annotate_click_to_segment,
    annotate_next_tile,
    annotate_record_correction,
    annotate_retrain,
    annotate_session_init,
)


def _write_pool(path: Path, n: int = 120, *, seed: int = 3) -> list[tuple[str, str]]:
    rng = random.Random(seed)
    classes = ["a", "b", "c"]
    rows = [(f"tile-{i:04d}", rng.choice(classes)) for i in range(n)]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["tile_id", "label"])
        for r in rows:
            writer.writerow(r)
    return rows


def test_session_init_creates_log_file(tmp_path: Path) -> None:
    pool = tmp_path / "pool.csv"
    _write_pool(pool)
    session = annotate_session_init(
        pool_csv=pool,
        out_dir=tmp_path / "session",
        annotator_id="dr-a",
    )
    assert session["annotator_id"] == "dr-a"
    assert session["classes"] == ["a", "b", "c"]
    assert session["queue"]  # non-empty
    log_path = Path(session["log_path"])  # type: ignore[arg-type]
    assert log_path.parent.exists()


def test_session_init_missing_pool_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="pool CSV"):
        annotate_session_init(
            pool_csv=tmp_path / "missing.csv",
            out_dir=tmp_path / "session",
        )


def test_session_init_bad_pool_raises(tmp_path: Path) -> None:
    # CSV without tile_id column.
    bad = tmp_path / "bad.csv"
    bad.write_text("foo,bar\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="tile_id"):
        annotate_session_init(pool_csv=bad, out_dir=tmp_path / "session")


def test_next_tile_advances_after_correction(tmp_path: Path) -> None:
    pool = tmp_path / "pool.csv"
    _write_pool(pool)
    session = annotate_session_init(pool_csv=pool, out_dir=tmp_path / "session")
    tile = annotate_next_tile(session)
    assert tile["tile_id"]
    assert tile["predicted_label"] in session["classes"]  # type: ignore[operator]

    session2 = annotate_record_correction(
        session,
        tile_id=str(tile["tile_id"]),
        corrected_label=session["classes"][0],  # type: ignore[index]
    )
    assert session2["cursor"] == 1
    assert session2["n_corrections"] == 1

    # Logger file exists + has the row.
    log_path = Path(session2["log_path"])  # type: ignore[arg-type]
    rows = list(csv.DictReader(log_path.open()))
    assert len(rows) == 1
    assert rows[0]["tile_id"] == tile["tile_id"]


def test_record_correction_rejects_unknown_label(tmp_path: Path) -> None:
    pool = tmp_path / "pool.csv"
    _write_pool(pool)
    session = annotate_session_init(pool_csv=pool, out_dir=tmp_path / "session")
    tile = annotate_next_tile(session)
    with pytest.raises(ValueError, match="not in classes"):
        annotate_record_correction(
            session,
            tile_id=str(tile["tile_id"]),
            corrected_label="not-a-class",
        )


def test_retrain_returns_metrics(tmp_path: Path) -> None:
    pool = tmp_path / "pool.csv"
    _write_pool(pool)
    session = annotate_session_init(pool_csv=pool, out_dir=tmp_path / "session")
    # Record 5 corrections to give the retrain something to work with.
    for _ in range(5):
        tile = annotate_next_tile(session)
        tid = str(tile["tile_id"])
        truth = session["oracle_truth"][tid]  # type: ignore[index]
        session = annotate_record_correction(session, tile_id=tid, corrected_label=truth)
    result = annotate_retrain(session)
    assert result["iteration"] == 1
    assert result["ece_before"] >= 0.0
    assert result["ece_after"] >= 0.0
    assert 0.0 <= result["accuracy_after"] <= 1.0
    assert result["n_labelled"] > 0


def test_click_to_segment_returns_mask_array(tmp_path: Path) -> None:
    size = 128
    img = np.full((size, size, 3), 240, dtype=np.uint8)
    yy, xx = np.mgrid[:size, :size]
    blob = np.sqrt((yy - size // 2) ** 2 + (xx - size // 2) ** 2) < size // 4
    img[blob] = np.array([100, 60, 120], dtype=np.uint8)
    mask = annotate_click_to_segment(img, point=(64, 64))
    assert mask.shape == (size, size)
    assert mask.dtype.kind in {"i", "u"}


def test_session_exhausts_after_all_tiles(tmp_path: Path) -> None:
    pool = tmp_path / "pool.csv"
    rows = _write_pool(pool, n=20)
    session = annotate_session_init(
        pool_csv=pool,
        out_dir=tmp_path / "session",
        seed_size=5,
        holdout_fraction=0.25,
    )
    # Drain the queue by recording each tile.
    drained = 0
    while True:
        tile = annotate_next_tile(session)
        if not tile["tile_id"]:
            break
        tid = str(tile["tile_id"])
        truth = session["oracle_truth"][tid]  # type: ignore[index]
        session = annotate_record_correction(session, tile_id=tid, corrected_label=truth)
        drained += 1
        if drained > len(rows):  # safety
            break
    final = annotate_next_tile(session)
    assert final["remaining"] == 0
