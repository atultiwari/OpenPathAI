"""Phase 11 — RunManifest → audit DB round-trip via ``import_manifest``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from openpathai.safety.audit import AuditDB, ManifestImportError, import_manifest, preview_manifest


def _manifest_payload(run_id: str = "colab-run-001", **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "run_id": run_id,
        "pipeline_id": "supervised-tile-classification",
        "pipeline_graph_hash": "abc123",
        "timestamp_start": "2026-03-01T12:00:00+00:00",
        "timestamp_end": "2026-03-01T12:05:00+00:00",
        "mode": "exploratory",
        "environment": {"git_commit": "deadbeef", "tier": "colab"},
        "cache_stats": {"hits": 5, "misses": 2},
    }
    payload.update(overrides)
    return payload


def _write_manifest(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_import_manifest_round_trip(tmp_path: Path) -> None:
    payload = _manifest_payload()
    manifest = _write_manifest(tmp_path / "m.json", payload)
    db = AuditDB.open_path(tmp_path / "audit.db")

    entry = import_manifest(manifest, db=db)

    assert entry.run_id == payload["run_id"]
    assert entry.kind == "pipeline"
    assert entry.mode == "exploratory"
    assert entry.pipeline_yaml_hash == payload["pipeline_graph_hash"]
    assert entry.graph_hash == payload["pipeline_graph_hash"]
    assert entry.git_commit == "deadbeef"
    assert entry.tier == "colab"
    assert entry.status == "success"
    assert entry.timestamp_start == payload["timestamp_start"]
    assert entry.timestamp_end == payload["timestamp_end"]

    # Row actually lives in the DB.
    loaded = db.get_run(entry.run_id)
    assert loaded is not None
    assert loaded.run_id == entry.run_id


def test_import_manifest_is_idempotent(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    manifest = _write_manifest(tmp_path / "m.json", _manifest_payload())
    db = AuditDB.open_path(tmp_path / "audit.db")

    first = import_manifest(manifest, db=db)
    with caplog.at_level("WARNING", logger="openpathai.safety.audit.sync"):
        second = import_manifest(manifest, db=db)

    assert first.run_id == second.run_id
    # Still exactly one row in the DB for that run_id.
    rows = db.list_runs()
    assert len([r for r in rows if r.run_id == first.run_id]) == 1
    assert any("already imported" in rec.message for rec in caplog.records)


def test_import_manifest_missing_file(tmp_path: Path) -> None:
    db = AuditDB.open_path(tmp_path / "audit.db")
    with pytest.raises(ManifestImportError, match="not found"):
        import_manifest(tmp_path / "does-not-exist.json", db=db)


def test_import_manifest_rejects_non_json(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("this is not json", encoding="utf-8")
    db = AuditDB.open_path(tmp_path / "audit.db")
    with pytest.raises(ManifestImportError, match="not a valid JSON"):
        import_manifest(bad, db=db)


def test_import_manifest_rejects_non_mapping(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(["not", "a", "mapping"]), encoding="utf-8")
    db = AuditDB.open_path(tmp_path / "audit.db")
    with pytest.raises(ManifestImportError, match="JSON mapping"):
        import_manifest(bad, db=db)


def test_import_manifest_requires_run_id(tmp_path: Path) -> None:
    payload = _manifest_payload()
    del payload["run_id"]
    manifest = _write_manifest(tmp_path / "m.json", payload)
    db = AuditDB.open_path(tmp_path / "audit.db")
    with pytest.raises(ManifestImportError, match="run_id"):
        import_manifest(manifest, db=db)


def test_import_manifest_requires_pipeline_graph_hash(tmp_path: Path) -> None:
    payload = _manifest_payload()
    del payload["pipeline_graph_hash"]
    manifest = _write_manifest(tmp_path / "m.json", payload)
    db = AuditDB.open_path(tmp_path / "audit.db")
    with pytest.raises(ManifestImportError, match="pipeline_graph_hash"):
        import_manifest(manifest, db=db)


def test_preview_manifest_does_not_write(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path / "m.json", _manifest_payload())
    db = AuditDB.open_path(tmp_path / "audit.db")

    preview = preview_manifest(manifest)

    assert preview["run_id"] == "colab-run-001"
    assert preview["kind"] == "pipeline"
    assert preview["mode"] == "exploratory"
    assert preview["git_commit"] == "deadbeef"
    assert preview["tier"] == "colab"
    assert preview["status"] == "success"
    assert preview["metrics"] == {"hits": 5, "misses": 2}
    # Absolute path so the user can confirm which manifest will be imported.
    assert Path(preview["manifest_path"]).is_absolute()
    # DB must remain empty.
    assert db.list_runs() == ()


def test_preview_manifest_handles_missing_environment(tmp_path: Path) -> None:
    payload = _manifest_payload()
    payload.pop("environment", None)
    payload.pop("cache_stats", None)
    manifest = _write_manifest(tmp_path / "m.json", payload)

    preview = preview_manifest(manifest)

    assert preview["git_commit"] == ""
    assert preview["tier"] == "unknown"
    assert preview["metrics"] == {}


def test_import_manifest_preserves_custom_run_id(tmp_path: Path) -> None:
    payload = _manifest_payload(run_id="my-custom-id-42")
    manifest = _write_manifest(tmp_path / "m.json", payload)
    db = AuditDB.open_path(tmp_path / "audit.db")

    entry = import_manifest(manifest, db=db)

    assert entry.run_id == "my-custom-id-42"
    loaded = db.get_run("my-custom-id-42")
    assert loaded is not None
