"""PHI contract — master-plan §17 + iron rule #8 of CLAUDE.md.

These tests are the only thing standing between an accidental path
leak and ``audit.db``. Treat failures here as P0.
"""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from openpathai.safety import AnalysisResult, BorderlineDecision, ClassProbability
from openpathai.safety.audit import AuditDB, hash_filename, log_analysis
from openpathai.safety.audit.phi import PHI_PARAM_KEYS, strip_phi

# --- hash_filename ---------------------------------------------------------


def test_hash_filename_basename_only() -> None:
    """Hash of a full PHI path must equal the hash of the basename."""
    full = "/Users/dr-smith/phi/case_042/slide_a.svs"
    basename = "slide_a.svs"
    assert hash_filename(full) == hash_filename(basename)


def test_hash_filename_deterministic() -> None:
    assert hash_filename("x.png") == hash_filename("x.png")


def test_hash_filename_differs_by_basename() -> None:
    assert hash_filename("a.png") != hash_filename("b.png")


def test_hash_filename_accepts_path_object() -> None:
    assert hash_filename(Path("/phi/x.png")) == hash_filename("x.png")


def test_hash_filename_empty() -> None:
    assert hash_filename("") == hashlib.sha256(b"").hexdigest()


# --- strip_phi -------------------------------------------------------------


def test_strip_phi_drops_path_keys() -> None:
    cleaned = strip_phi(
        {
            "path": "/Users/phi/x.png",
            "tile_path": "/home/doc/y.png",
            "file_path": "/anywhere/z.png",
            "epochs": 10,
            "val_acc": 0.9,
        }
    )
    assert "path" not in cleaned
    assert "tile_path" not in cleaned
    assert "file_path" not in cleaned
    assert cleaned["epochs"] == 10
    assert cleaned["val_acc"] == 0.9


def test_strip_phi_redacts_path_values() -> None:
    cleaned = strip_phi(
        {
            "comment": "/Users/phi/something",
            "note": "~/tilde/path",
            "safe": "some prose without slashes",
        }
    )
    assert cleaned["comment"] == "<redacted-path>"
    assert cleaned["note"] == "<redacted-path>"
    assert cleaned["safe"] == "some prose without slashes"


def test_strip_phi_recursive() -> None:
    cleaned = strip_phi(
        {
            "nested": {
                "path": "/Users/phi/x",
                "kept": 1,
            },
        }
    )
    assert cleaned["nested"] == {"kept": 1}


def test_strip_phi_none_returns_empty_dict() -> None:
    assert strip_phi(None) == {}


def test_phi_param_keys_case_insensitive_check() -> None:
    cleaned = strip_phi({"PATH": "/Users/whatever", "OK": 1})
    assert "PATH" not in cleaned
    assert cleaned["OK"] == 1


def test_phi_param_keys_includes_common_variants() -> None:
    for key in ("path", "filename", "tile_path", "input"):
        assert key in PHI_PARAM_KEYS


# --- Grep-style guard: a real log_analysis call never leaks -----------------


def test_log_analysis_never_writes_phi_to_db(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENPATHAI_HOME", str(tmp_path))
    # New DB
    db = AuditDB.open_default()
    result = AnalysisResult(
        image_sha256="f" * 64,
        model_name="resnet18",
        explainer_name="gradcam",
        probabilities=(
            ClassProbability("normal", 0.1),
            ClassProbability("tumour", 0.9),
        ),
        borderline=BorderlineDecision(1, 0.9, "positive", "high", 0.4, 0.7),
        timestamp=datetime(2026, 4, 24, tzinfo=UTC),
    )
    log_analysis(
        result,
        input_path="/Users/dr-smith/phi/secret_case_042.svs",
        db=db,
    )

    # Read every column of every row and grep.
    with sqlite3.connect(db.path) as conn:
        conn.row_factory = sqlite3.Row
        rows = list(conn.execute("SELECT * FROM analyses").fetchall()) + list(
            conn.execute("SELECT * FROM runs").fetchall()
        )
    assert rows, "expected at least one row written"
    for row in rows:
        for value in row.keys():  # noqa: SIM118 — .keys() required on Row
            cell = row[value]
            if cell is None:
                continue
            text = str(cell)
            assert "/Users/" not in text, f"PHI leak in column {value}: {text!r}"
            assert "/home/" not in text, f"PHI leak in column {value}: {text!r}"
            assert "secret_case_042.svs" not in text, f"basename leak in column {value}: {text!r}"
