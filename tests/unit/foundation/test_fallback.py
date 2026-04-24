"""Fallback resolver behaviour — master-plan §11.5 contract."""

from __future__ import annotations

import pytest

from openpathai.foundation import (
    FallbackDecision,
    GatedAccessError,
    default_foundation_registry,
    resolve_backbone,
)


def _no_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HUGGINGFACE_HUB_TOKEN", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)


def test_open_backbone_resolves_to_itself(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_token(monkeypatch)
    reg = default_foundation_registry()
    decision = resolve_backbone("dinov2_vits14", registry=reg)
    assert decision.requested_id == "dinov2_vits14"
    assert decision.resolved_id == "dinov2_vits14"
    assert decision.reason == "ok"


def test_gated_falls_back_when_token_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_token(monkeypatch)
    reg = default_foundation_registry()
    decision = resolve_backbone("uni", registry=reg)
    assert decision.requested_id == "uni"
    assert decision.resolved_id == "dinov2_vits14"
    assert decision.reason == "hf_token_missing"
    assert "MahmoodLab/UNI" in decision.message
    assert decision.hf_token_present is False


def test_stub_falls_back_when_token_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_token(monkeypatch)
    reg = default_foundation_registry()
    for stub_id in ("conch", "virchow2", "prov_gigapath", "hibou", "uni2_h"):
        decision = resolve_backbone(stub_id, registry=reg)
        assert decision.resolved_id == "dinov2_vits14"
        assert decision.reason == "hf_token_missing"


def test_strict_mode_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_token(monkeypatch)
    reg = default_foundation_registry()
    with pytest.raises(GatedAccessError, match="MahmoodLab"):
        resolve_backbone("uni", registry=reg, allow_fallback=False)


def test_unknown_id_raises_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_token(monkeypatch)
    reg = default_foundation_registry()
    with pytest.raises(ValueError, match="unknown foundation backbone"):
        resolve_backbone("nothing_here", registry=reg)


def test_ctranspath_weight_missing_falls_back(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """CTransPath's gated=True path trips when weights are absent."""
    # Set HF token so we get past the early bail-out and exercise the
    # weight-file-missing branch instead.
    monkeypatch.setenv("HF_TOKEN", "dummy-for-test")
    monkeypatch.setenv("OPENPATHAI_HOME", str(tmp_path))  # no ctranspath.pth here
    reg = default_foundation_registry()
    decision = resolve_backbone("ctranspath", registry=reg)
    assert decision.resolved_id == "dinov2_vits14"
    assert decision.reason in {"weight_file_missing", "hf_gated", "import_error"}


def test_fallback_decision_schema() -> None:
    dec = FallbackDecision(
        requested_id="uni",
        resolved_id="dinov2_vits14",
        reason="hf_token_missing",
        message="x",
        hf_token_present=False,
    )
    # Frozen + forbids extras.
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        FallbackDecision(
            requested_id="a",
            resolved_id="b",
            reason="ok",
            message="x",
            hf_token_present=False,
            extra_unknown="should fail",  # type: ignore[call-arg]
        )
    # No mutation (pydantic frozen models raise ValidationError on set).
    with pytest.raises(ValidationError):
        dec.resolved_id = "x"  # type: ignore[misc]
