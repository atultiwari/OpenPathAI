"""Unit tests for ``openpathai.pipeline.manifest``."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from openpathai.pipeline.manifest import (
    MANIFEST_VERSION,
    CacheStats,
    Environment,
    NodeRunRecord,
    RunManifest,
    capture_environment,
)


@pytest.mark.unit
def test_capture_environment_populates_fields() -> None:
    env = capture_environment()
    assert isinstance(env, Environment)
    assert env.openpathai_version
    assert env.python_version
    assert env.platform
    assert env.machine


@pytest.mark.unit
def test_cache_stats_total() -> None:
    stats = CacheStats(hits=3, misses=2)
    assert stats.total == 5


@pytest.mark.unit
def test_manifest_round_trips_through_json() -> None:
    env = Environment(
        openpathai_version="0.0.1.dev0",
        python_version="3.11.9",
        platform="Darwin-24.1.0-arm64-arm-64bit",
        machine="arm64",
        git_commit="deadbeef",
    )
    now = datetime(2026, 4, 23, 12, 0, 0, tzinfo=UTC)
    record = NodeRunRecord(
        step_id="a",
        op="math.double",
        cache_key="k",
        cache_hit=False,
        code_hash="h",
        started_at=now,
        ended_at=now,
        input_config={"value": 5},
        input_hashes={"__upstream__": ""},
        output_artifact_type="IntArtifact",
        output_hash="oh",
    )
    manifest = RunManifest(
        run_id="run-1",
        pipeline_id="toy",
        pipeline_graph_hash="g",
        mode="exploratory",
        timestamp_start=now,
        timestamp_end=now,
        environment=env,
        steps=[record],
        cache_stats=CacheStats(hits=0, misses=1),
        metrics={"ece": 0.01},
    )

    raw = manifest.to_json()
    reloaded = RunManifest.from_json(raw)
    assert reloaded == manifest
    assert reloaded.manifest_version == MANIFEST_VERSION


@pytest.mark.unit
def test_compute_graph_hash_is_deterministic() -> None:
    spec = {"id": "p", "steps": [{"id": "a", "op": "x"}]}
    spec_reordered = {"steps": [{"op": "x", "id": "a"}], "id": "p"}
    assert RunManifest.compute_graph_hash(spec) == RunManifest.compute_graph_hash(spec_reordered)
