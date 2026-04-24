"""UNI + CTransPath adapters — the gated / weight-file-missing paths.

These tests exercise every branch that doesn't need real gated HF
access or a real CTransPath checkpoint on disk: the happy-path
``.build()`` is covered by the opt-in ``OPENPATHAI_RUN_GATED=1``
variant, which we can't run in CI.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from openpathai.foundation.ctranspath import CTransPathAdapter
from openpathai.foundation.fallback import GatedAccessError
from openpathai.foundation.stubs import (
    CONCHStub,
    HibouStub,
    ProvGigaPathStub,
    UNI2HStub,
    Virchow2Stub,
)
from openpathai.foundation.uni import UNIAdapter


def test_uni_build_without_token_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HUGGINGFACE_HUB_TOKEN", raising=False)
    adapter = UNIAdapter()
    with pytest.raises(GatedAccessError, match="gated"):
        adapter.build()


def test_uni_preprocess_delegates_to_dinov2() -> None:
    pytest.importorskip("torch")
    adapter = UNIAdapter()
    image = (np.random.default_rng(0).random((224, 224, 3)) * 255).astype(np.uint8)
    tensor = adapter.preprocess(image)
    # Same shape as DINOv2's.
    assert tensor.shape == (1, 3, 224, 224)


def test_ctranspath_build_without_weights_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENPATHAI_HOME", str(tmp_path))
    adapter = CTransPathAdapter()
    assert adapter._weight_path.parent.exists() is False
    with pytest.raises(FileNotFoundError, match=r"ctranspath\.pth"):
        adapter.build()


def test_ctranspath_preprocess_delegates_to_dinov2() -> None:
    pytest.importorskip("torch")
    adapter = CTransPathAdapter()
    image = (np.random.default_rng(0).random((224, 224, 3)) * 255).astype(np.uint8)
    tensor = adapter.preprocess(image)
    assert tensor.shape == (1, 3, 224, 224)


@pytest.mark.parametrize(
    "stub_cls", [UNI2HStub, CONCHStub, Virchow2Stub, ProvGigaPathStub, HibouStub]
)
def test_stub_build_raises_gated_access(stub_cls) -> None:
    stub = stub_cls()
    with pytest.raises(GatedAccessError, match="Phase 13 stub"):
        stub.build()


@pytest.mark.parametrize(
    "stub_cls", [UNI2HStub, CONCHStub, Virchow2Stub, ProvGigaPathStub, HibouStub]
)
def test_stub_embed_raises_gated_access(stub_cls) -> None:
    stub = stub_cls()
    with pytest.raises(GatedAccessError, match="stub adapter"):
        stub.embed(np.zeros((1, 3, 224, 224), dtype=np.float32))


def test_stub_preprocess_delegates_to_dinov2() -> None:
    """Stubs still need a working preprocess for Phase 16 GUI picker
    parity — they inherit from the same DINOv2 path."""
    pytest.importorskip("torch")
    image = (np.random.default_rng(0).random((224, 224, 3)) * 255).astype(np.uint8)
    tensor = CONCHStub().preprocess(image)
    assert tensor.shape == (1, 3, 224, 224)


def test_uni_citation_is_populated() -> None:
    adapter = UNIAdapter()
    assert "Chen" in adapter.citation
    assert adapter.hf_repo == "MahmoodLab/UNI"


def test_ctranspath_explicit_weight_path(tmp_path: Path) -> None:
    """Constructor override resolves to the caller-supplied path."""
    custom = tmp_path / "custom-weights.pth"
    adapter = CTransPathAdapter(weight_path=custom)
    assert adapter._weight_path == custom
    with pytest.raises(FileNotFoundError):
        adapter.build()
