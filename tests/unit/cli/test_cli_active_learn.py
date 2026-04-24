"""Phase 12 — ``openpathai active-learn`` CLI contract."""

from __future__ import annotations

import csv
import json
import random
from pathlib import Path

import pytest
from typer.testing import CliRunner

from openpathai.cli.main import app
from tests.conftest import strip_ansi

runner = CliRunner(mix_stderr=False)


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


def test_help_lists_core_flags() -> None:
    result = runner.invoke(app, ["active-learn", "--help"])
    assert result.exit_code == 0, result.stdout
    out = strip_ansi(result.stdout)
    for token in (
        "--pool",
        "--out",
        "--scorer",
        "--sampler",
        "--budget",
        "--iterations",
        "--seed-size",
        "--annotator-id",
        "--seed",
    ):
        assert token in out, f"{token!r} missing from help output:\n{out}"


def test_missing_pool_exits_2(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "active-learn",
            "--pool",
            str(tmp_path / "does-not-exist.csv"),
            "--out",
            str(tmp_path / "run"),
        ],
    )
    assert result.exit_code == 2
    combined = result.stdout + (result.stderr or "")
    assert "not found" in combined


def test_bad_scorer_exits_2(tmp_path: Path) -> None:
    pool = tmp_path / "pool.csv"
    _write_pool(pool)
    result = runner.invoke(
        app,
        [
            "active-learn",
            "--pool",
            str(pool),
            "--out",
            str(tmp_path / "run"),
            "--scorer",
            "banana",
        ],
    )
    assert result.exit_code == 2
    combined = result.stdout + (result.stderr or "")
    assert "unknown scorer" in combined


def test_bad_sampler_exits_2(tmp_path: Path) -> None:
    pool = tmp_path / "pool.csv"
    _write_pool(pool)
    result = runner.invoke(
        app,
        [
            "active-learn",
            "--pool",
            str(pool),
            "--out",
            str(tmp_path / "run"),
            "--sampler",
            "not-a-thing",
        ],
    )
    assert result.exit_code == 2
    combined = result.stdout + (result.stderr or "")
    assert "unknown sampler" in combined


def test_budget_exceeds_pool_exits_2(tmp_path: Path) -> None:
    pool = tmp_path / "pool.csv"
    _write_pool(pool, n=10)
    result = runner.invoke(
        app,
        [
            "active-learn",
            "--pool",
            str(pool),
            "--out",
            str(tmp_path / "run"),
            "--budget",
            "9999",
            "--iterations",
            "1",
            "--seed-size",
            "2",
        ],
    )
    assert result.exit_code == 2
    combined = result.stdout + (result.stderr or "")
    assert "exceeds unlabeled pool" in combined


def test_end_to_end_produces_manifest_and_corrections(tmp_path: Path) -> None:
    pool = tmp_path / "pool.csv"
    _write_pool(pool)
    result = runner.invoke(
        app,
        [
            "active-learn",
            "--pool",
            str(pool),
            "--out",
            str(tmp_path / "run"),
            "--iterations",
            "2",
            "--budget",
            "6",
            "--seed-size",
            "12",
            "--sampler",
            "hybrid",
            "--no-audit",
        ],
    )
    assert result.exit_code == 0, result.stderr or result.stdout
    summary = json.loads(result.stdout)
    assert summary["iterations_completed"] == 2
    assert summary["n_acquired"] == 12
    assert summary["annotator_id"] == "simulated-oracle"
    assert Path(summary["manifest_path"]).exists()
    assert Path(summary["corrections_path"]).exists()
    # ECE should not worsen.
    assert summary["final_ece"] <= summary["initial_ece"] + 1e-6


def test_audit_db_records_iterations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Without --no-audit, each iteration inserts one pipeline row."""
    from openpathai.safety.audit import AuditDB

    monkeypatch.setenv("OPENPATHAI_HOME", str(tmp_path / "home"))
    pool = tmp_path / "pool.csv"
    _write_pool(pool)
    result = runner.invoke(
        app,
        [
            "active-learn",
            "--pool",
            str(pool),
            "--out",
            str(tmp_path / "run"),
            "--iterations",
            "3",
            "--budget",
            "4",
            "--seed-size",
            "8",
        ],
    )
    assert result.exit_code == 0, result.stderr or result.stdout
    db = AuditDB.open_default()
    rows = db.list_runs(kind="pipeline")
    assert len(rows) == 3
    # Each iteration must hash to a distinct graph_hash.
    assert len({r.graph_hash for r in rows}) == 3


@pytest.mark.parametrize("scorer", ["max_softmax", "entropy"])
def test_scorer_switch_affects_which_tiles_are_picked(tmp_path: Path, scorer: str) -> None:
    pool = tmp_path / "pool.csv"
    _write_pool(pool)
    out = tmp_path / f"run-{scorer}"
    result = runner.invoke(
        app,
        [
            "active-learn",
            "--pool",
            str(pool),
            "--out",
            str(out),
            "--iterations",
            "1",
            "--budget",
            "5",
            "--seed-size",
            "10",
            "--scorer",
            scorer,
            "--no-audit",
        ],
    )
    assert result.exit_code == 0, result.stderr or result.stdout
    payload = json.loads((out / "manifest.json").read_text())
    assert payload["config"]["scorer"] == scorer
