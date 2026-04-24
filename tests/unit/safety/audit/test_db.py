"""AuditDB round-trip: insert + list + get + filter + update + delete."""

from __future__ import annotations

from pathlib import Path

import pytest

from openpathai.safety.audit import AnalysisEntry, AuditDB, AuditEntry


@pytest.fixture
def db(tmp_path: Path) -> AuditDB:
    return AuditDB.open_path(tmp_path / "audit.db")


def test_insert_run_round_trip(db: AuditDB) -> None:
    entry = db.insert_run(
        kind="training",
        metrics={"val_acc": 0.9},
        manifest_path="/tmp/whatever",  # PHI-looking path exercises the guard
    )
    assert isinstance(entry, AuditEntry)
    assert entry.kind == "training"
    loaded = db.get_run(entry.run_id)
    assert loaded is not None
    assert loaded.run_id == entry.run_id
    assert loaded.metrics_json is not None
    assert "val_acc" in loaded.metrics_json


def test_list_runs_filter_by_kind(db: AuditDB) -> None:
    db.insert_run(kind="pipeline", manifest_path="")
    db.insert_run(kind="training", manifest_path="")
    pipeline = db.list_runs(kind="pipeline")
    training = db.list_runs(kind="training")
    assert {r.kind for r in pipeline} == {"pipeline"}
    assert {r.kind for r in training} == {"training"}


def test_list_runs_filter_by_status(db: AuditDB) -> None:
    db.insert_run(kind="training", manifest_path="", status="running")
    done = db.insert_run(kind="training", manifest_path="", status="success")
    hits = db.list_runs(status="success")
    assert {r.run_id for r in hits} == {done.run_id}


def test_update_run_status(db: AuditDB) -> None:
    entry = db.insert_run(kind="training", manifest_path="", status="running")
    db.update_run_status(entry.run_id, status="success", metrics={"acc": 0.95})
    loaded = db.get_run(entry.run_id)
    assert loaded is not None
    assert loaded.status == "success"
    assert loaded.metrics_json is not None and "acc" in loaded.metrics_json


def test_insert_analysis_round_trip(db: AuditDB) -> None:
    entry = db.insert_analysis(
        filename_hash="abc" * 20,
        image_sha256="f" * 64,
        prediction="tumour",
        confidence=0.87,
        decision="positive",
        band="high",
        model_id="resnet18",
    )
    assert isinstance(entry, AnalysisEntry)
    loaded = db.get_analysis(entry.analysis_id)
    assert loaded is not None
    assert loaded.prediction == "tumour"
    assert loaded.confidence == pytest.approx(0.87)
    assert loaded.decision == "positive"
    assert loaded.band == "high"


def test_list_analyses_filter_by_run(db: AuditDB) -> None:
    run = db.insert_run(kind="pipeline", manifest_path="")
    own = db.insert_analysis(
        run_id=run.run_id,
        filename_hash="own",
        image_sha256="1" * 64,
        prediction="a",
        confidence=0.5,
        decision="review",
        band="between",
        model_id="resnet18",
    )
    db.insert_analysis(
        filename_hash="orphan",
        image_sha256="2" * 64,
        prediction="b",
        confidence=0.5,
        decision="review",
        band="between",
        model_id="resnet18",
    )
    scoped = db.list_analyses(run_id=run.run_id)
    assert {a.analysis_id for a in scoped} == {own.analysis_id}


def test_delete_before(db: AuditDB) -> None:
    old = db.insert_run(
        kind="pipeline",
        manifest_path="",
        timestamp_start="1999-01-01T00:00:00+00:00",
    )
    new = db.insert_run(
        kind="pipeline",
        manifest_path="",
        timestamp_start="2999-01-01T00:00:00+00:00",
    )
    deleted = db.delete_before("2000-01-01T00:00:00+00:00")
    assert deleted["runs"] == 1
    assert db.get_run(old.run_id) is None
    assert db.get_run(new.run_id) is not None


def test_stats(db: AuditDB) -> None:
    db.insert_run(kind="pipeline", manifest_path="")
    db.insert_run(kind="training", manifest_path="")
    db.insert_run(kind="training", manifest_path="")
    s = db.stats()
    assert s["schema_version"] == 1
    assert s["runs"] == 3
    assert s["runs_per_kind"] == {"pipeline": 1, "training": 2}


def test_two_connections_see_each_other(tmp_path: Path) -> None:
    path = tmp_path / "audit.db"
    a = AuditDB.open_path(path)
    b = AuditDB.open_path(path)
    entry = a.insert_run(kind="training", manifest_path="")
    assert b.get_run(entry.run_id) is not None
