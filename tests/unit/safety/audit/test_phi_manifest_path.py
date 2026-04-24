"""Iron rule #8 — ``runs.manifest_path`` must never persist raw filesystem
paths (parent directories can encode patient context)."""

from __future__ import annotations

from pathlib import Path

from openpathai.safety.audit import AuditDB
from openpathai.safety.audit.phi import redact_manifest_path


def test_redact_manifest_path_strips_parent(tmp_path: Path) -> None:
    redacted = redact_manifest_path("/Users/dr-smith/patient_042/runs/manifest.json")
    assert redacted.startswith("manifest.json#")
    # Parent tokens must not leak verbatim.
    assert "dr-smith" not in redacted
    assert "patient_042" not in redacted
    # 8-char hex suffix.
    suffix = redacted.split("#", 1)[1]
    assert len(suffix) == 8
    assert all(c in "0123456789abcdef" for c in suffix)


def test_redact_manifest_path_same_dir_collates() -> None:
    a = redact_manifest_path("/patients/A/manifest.json")
    b = redact_manifest_path("/patients/A/manifest.json")
    c = redact_manifest_path("/patients/B/manifest.json")
    assert a == b
    assert a != c


def test_redact_manifest_path_empty_passes_through() -> None:
    assert redact_manifest_path("") == ""


def test_audit_insert_redacts_manifest_path(tmp_path: Path) -> None:
    db = AuditDB.open_path(tmp_path / "audit.db")
    entry = db.insert_run(
        kind="pipeline",
        manifest_path="/Users/dr-smith/patient_042/runs/manifest.json",
    )
    loaded = db.get_run(entry.run_id)
    assert loaded is not None
    assert "dr-smith" not in loaded.manifest_path
    assert "patient_042" not in loaded.manifest_path
    assert loaded.manifest_path.startswith("manifest.json#")


def test_audit_entry_tolerates_unknown_columns(tmp_path: Path) -> None:
    """Future migrations can add columns without bricking existing readers.

    Simulated here by constructing ``AuditEntry`` directly with an
    unknown extra key — should be silently dropped rather than raising.
    """
    from openpathai.safety.audit.db import AuditEntry

    entry = AuditEntry(
        run_id="run-1",
        kind="pipeline",
        mode="exploratory",
        timestamp_start="2026-04-24T12:00:00+00:00",
        pipeline_yaml_hash="",
        graph_hash="",
        git_commit="",
        tier="local",
        status="success",
        manifest_path="",
        future_column="some new value",  # type: ignore[call-arg]
    )
    assert entry.run_id == "run-1"
    # The unknown field must not appear on the model dump.
    assert "future_column" not in entry.model_dump()
