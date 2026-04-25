"""Gated-access fallback resolver (master-plan §11.5).

When the caller requests a gated backbone (UNI / CONCH / Virchow2 /
Prov-GigaPath / Hibou / UNI2-h / CTransPath-weights) but the local
environment cannot load it — no HF token, weight file missing, the
adapter itself raises on import — we fall back to **DINOv2-small**
(the open, always-available default) and surface a banner so the
downstream CLI / manifest / (Phase 16) GUI can explain what happened.

The returned :class:`FallbackDecision` is persisted into the Phase 8
audit row's ``metrics_json`` (``resolved_backbone_id`` +
``fallback_reason``) so every run manifest records the model that
*actually* ran, not the one the user asked for.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

from openpathai.config import hf as _hf_config

if TYPE_CHECKING:  # pragma: no cover - type-only
    from openpathai.foundation.adapter import FoundationAdapter
    from openpathai.foundation.registry import FoundationRegistry

__all__ = [
    "FALLBACK_BACKBONE_ID",
    "FallbackDecision",
    "FallbackReason",
    "GatedAccessError",
    "build_resolved_adapter",
    "hf_token_present",
    "resolve_backbone",
    "resolve_backbone_and_build",
]


FallbackReason = Literal[
    "ok",
    "hf_token_missing",
    "hf_gated",
    "weight_file_missing",
    "import_error",
]


FALLBACK_BACKBONE_ID = "dinov2_vits14"
"""The always-available open default we fall back to."""


class GatedAccessError(RuntimeError):
    """Raised from a gated adapter's ``.build()`` when weights cannot
    be loaded and the caller explicitly disabled fallback."""


class FallbackDecision(BaseModel):
    """What :func:`resolve_backbone` returned.

    Persisted verbatim into Phase 8 audit ``metrics_json`` so manifests
    always record the actual model used (master-plan §11.5 clause 3).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    requested_id: str = Field(min_length=1)
    resolved_id: str = Field(min_length=1)
    reason: FallbackReason
    message: str
    hf_token_present: bool


def hf_token_present() -> bool:
    """``True`` when an HF token is resolvable from any source.

    Resolution order (highest precedence first) is owned by
    :mod:`openpathai.config.hf`:

    1. ``$OPENPATHAI_HOME/secrets.json`` (set via canvas Settings card).
    2. ``HF_TOKEN`` env var (transformers convention).
    3. ``HUGGING_FACE_HUB_TOKEN`` env var (huggingface-hub CLI convention).
    """
    return _hf_config.is_token_present()


def resolve_backbone(
    requested_id: str,
    *,
    registry: FoundationRegistry,
    allow_fallback: bool = True,
) -> FallbackDecision:
    """Return a :class:`FallbackDecision` for ``requested_id``.

    **Two-step contract:** this function only reports which backbone will
    run (``decision.resolved_id``); it does not return the built adapter.
    If you need the actual adapter — e.g. to embed tiles — call
    :func:`build_resolved_adapter` or use the combined
    :func:`resolve_backbone_and_build` helper. Iron rule #11 is preserved
    either way because the manifest already records ``resolved_id``.

    The function never raises on its own — it calls the adapter's
    ``.build()`` inside a broad ``try`` so any import or gated-access
    error becomes a fallback rather than a crash. With
    ``allow_fallback=False`` we re-raise as :class:`GatedAccessError``
    so the caller can decide to hard-fail.
    """
    token_present = hf_token_present()
    try:
        adapter = registry.get(requested_id)
    except KeyError as exc:
        raise ValueError(
            f"unknown foundation backbone {requested_id!r}; run "
            f"`openpathai foundation list` to see the registry."
        ) from exc

    if not adapter.gated:
        return FallbackDecision(
            requested_id=requested_id,
            resolved_id=requested_id,
            reason="ok",
            message=f"{requested_id} is open access; no fallback needed.",
            hf_token_present=token_present,
        )

    if not token_present:
        decision = FallbackDecision(
            requested_id=requested_id,
            resolved_id=FALLBACK_BACKBONE_ID,
            reason="hf_token_missing",
            message=(
                f"{requested_id} requires Hugging Face gated access. "
                "Set HUGGINGFACE_HUB_TOKEN (or HF_TOKEN) and request "
                f"access to {adapter.hf_repo!r}. Using "
                f"{FALLBACK_BACKBONE_ID} as fallback; expect a 3-5 pp "
                "accuracy drop on benchmarks."
            ),
            hf_token_present=False,
        )
        if not allow_fallback:
            raise GatedAccessError(decision.message)
        return decision

    # Token present — try to actually build. A gated-but-accessible
    # build() may succeed (returns the real model) or may fail with
    # gated-access / weight-missing / other import errors — all three
    # become a fallback.
    try:
        adapter.build(pretrained=True)
    except GatedAccessError as exc:
        decision = FallbackDecision(
            requested_id=requested_id,
            resolved_id=FALLBACK_BACKBONE_ID,
            reason="hf_gated",
            message=(
                f"{requested_id} gated access build failed: {exc!s}. "
                f"Using {FALLBACK_BACKBONE_ID} as fallback."
            ),
            hf_token_present=True,
        )
        if not allow_fallback:
            raise
        return decision
    except FileNotFoundError as exc:
        decision = FallbackDecision(
            requested_id=requested_id,
            resolved_id=FALLBACK_BACKBONE_ID,
            reason="weight_file_missing",
            message=(
                f"{requested_id} weight file missing: {exc!s}. Place "
                "the checkpoint under $OPENPATHAI_HOME/models/ and "
                f"retry. Using {FALLBACK_BACKBONE_ID} as fallback."
            ),
            hf_token_present=True,
        )
        if not allow_fallback:
            raise GatedAccessError(decision.message) from exc
        return decision
    except ImportError as exc:
        decision = FallbackDecision(
            requested_id=requested_id,
            resolved_id=FALLBACK_BACKBONE_ID,
            reason="import_error",
            message=(
                f"{requested_id} adapter failed to import its backend "
                f"({exc!s}). Using {FALLBACK_BACKBONE_ID} as fallback."
            ),
            hf_token_present=True,
        )
        if not allow_fallback:
            raise GatedAccessError(decision.message) from exc
        return decision

    return FallbackDecision(
        requested_id=requested_id,
        resolved_id=requested_id,
        reason="ok",
        message=f"{requested_id} loaded from gated source (token present).",
        hf_token_present=True,
    )


def build_resolved_adapter(
    decision: FallbackDecision,
    *,
    registry: FoundationRegistry,
) -> FoundationAdapter:
    """Return the built adapter that matches ``decision.resolved_id``.

    Use this after :func:`resolve_backbone` when you need to actually
    embed tiles — not just report the resolution in a manifest. For
    callers that want a single call, see
    :func:`resolve_backbone_and_build`.
    """
    try:
        adapter = registry.get(decision.resolved_id)
    except KeyError as exc:  # pragma: no cover - defensive; resolver guarantees resolved_id
        raise ValueError(
            f"resolved backbone {decision.resolved_id!r} is not registered; "
            f"registry has drifted from the fallback resolver."
        ) from exc
    adapter.build(pretrained=True)
    return adapter


def resolve_backbone_and_build(
    requested_id: str,
    *,
    registry: FoundationRegistry,
    allow_fallback: bool = True,
) -> tuple[FallbackDecision, FoundationAdapter]:
    """Resolve + build in one call.

    Returns both the :class:`FallbackDecision` (for manifest persistence)
    and the built adapter (for embedding). Callers that only need the
    decision string can keep using :func:`resolve_backbone` alone.
    """
    decision = resolve_backbone(requested_id, registry=registry, allow_fallback=allow_fallback)
    adapter = build_resolved_adapter(decision, registry=registry)
    return decision, adapter
