"""Unit tests for ``openpathai.pipeline.cache``."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from openpathai.pipeline.cache import CacheEntryMeta, ContentAddressableCache
from openpathai.pipeline.schema import IntArtifact


@pytest.fixture
def cache(tmp_path: Path) -> ContentAddressableCache:
    return ContentAddressableCache(root=tmp_path / "cache")


@pytest.mark.unit
def test_key_is_deterministic() -> None:
    k1 = ContentAddressableCache.key(
        node_id="n",
        code_hash="h",
        input_config={"a": 1, "b": 2},
        upstream_hashes=["x", "y"],
    )
    k2 = ContentAddressableCache.key(
        node_id="n",
        code_hash="h",
        input_config={"b": 2, "a": 1},  # different insertion order
        upstream_hashes=["y", "x"],  # different order — should sort
    )
    assert k1 == k2


@pytest.mark.unit
def test_key_differs_when_inputs_change() -> None:
    k1 = ContentAddressableCache.key("n", "h", {"a": 1}, [])
    k2 = ContentAddressableCache.key("n", "h", {"a": 2}, [])
    assert k1 != k2


@pytest.mark.unit
def test_key_differs_when_code_hash_changes() -> None:
    k1 = ContentAddressableCache.key("n", "h1", {"a": 1}, [])
    k2 = ContentAddressableCache.key("n", "h2", {"a": 1}, [])
    assert k1 != k2


@pytest.mark.unit
def test_put_then_get_round_trips(cache: ContentAddressableCache) -> None:
    artifact = IntArtifact(value=7)
    key = "abc123"
    cache.put(
        key,
        node_id="n",
        code_hash="h",
        input_config={"a": 1},
        upstream_hashes=[],
        artifact=artifact,
    )
    assert cache.has(key)
    loaded = cache.get(key, IntArtifact)
    assert loaded == artifact


@pytest.mark.unit
def test_get_miss_returns_none(cache: ContentAddressableCache) -> None:
    assert cache.get("does-not-exist", IntArtifact) is None


@pytest.mark.unit
def test_invalidate_removes_entry(cache: ContentAddressableCache) -> None:
    cache.put(
        "k",
        node_id="n",
        code_hash="h",
        input_config={},
        upstream_hashes=[],
        artifact=IntArtifact(value=1),
    )
    assert cache.has("k")
    assert cache.invalidate("k") is True
    assert not cache.has("k")
    # Invalidating a nonexistent key is a no-op that returns False.
    assert cache.invalidate("k") is False


@pytest.mark.unit
def test_clear_all(cache: ContentAddressableCache) -> None:
    for i in range(3):
        cache.put(
            f"k{i}",
            node_id="n",
            code_hash="h",
            input_config={"i": i},
            upstream_hashes=[],
            artifact=IntArtifact(value=i),
        )
    assert cache.clear() == 3
    assert not cache.has("k0")


@pytest.mark.unit
def test_clear_older_than_days_respects_threshold(
    cache: ContentAddressableCache,
) -> None:
    cache.put(
        "fresh",
        node_id="n",
        code_hash="h",
        input_config={},
        upstream_hashes=[],
        artifact=IntArtifact(value=1),
    )
    # Write an "old" entry by overwriting its meta timestamp.
    cache.put(
        "old",
        node_id="n",
        code_hash="h",
        input_config={},
        upstream_hashes=[],
        artifact=IntArtifact(value=2),
    )
    old_meta_path = cache.root / "old" / "meta.json"
    old_meta = CacheEntryMeta.model_validate_json(
        old_meta_path.read_text(encoding="utf-8")
    ).model_copy(update={"created_at": time.time() - 30 * 86400.0})
    old_meta_path.write_text(old_meta.model_dump_json(), encoding="utf-8")

    removed = cache.clear(older_than_days=7)
    assert removed == 1
    assert cache.has("fresh")
    assert not cache.has("old")


@pytest.mark.unit
def test_put_with_basemodel_config(cache: ContentAddressableCache) -> None:
    from pydantic import BaseModel

    class Cfg(BaseModel):
        a: int
        b: str

    cfg = Cfg(a=1, b="hello")
    cache.put(
        "model-cfg",
        node_id="n",
        code_hash="h",
        input_config=cfg,
        upstream_hashes=[],
        artifact=IntArtifact(value=99),
    )
    meta = cache.get_meta("model-cfg")
    assert meta is not None
    assert meta.artifact_type == "IntArtifact"
