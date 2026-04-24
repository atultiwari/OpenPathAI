"""Stub adapters for gated foundation backbones not yet wired end-to-end.

Every stub:

* registers in :func:`openpathai.foundation.default_foundation_registry`
  so ``openpathai foundation list`` includes it;
* knows its HF repo id + license + citation + embedding dim (for
  tabular listing + downstream MIL shape-checking);
* raises :class:`~openpathai.foundation.fallback.GatedAccessError`
  from :meth:`build` so :func:`resolve_backbone` substitutes DINOv2.

When a user needs one of these for real (or Phase 15 wires CONCH's
zero-shot surface), promote the stub to a full adapter in its own
module and drop it from :mod:`~openpathai.foundation.stubs`. The
registry loader picks up the new class automatically.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from openpathai.foundation.fallback import GatedAccessError

__all__ = [
    "CONCHStub",
    "HibouStub",
    "ProvGigaPathStub",
    "UNI2HStub",
    "Virchow2Stub",
]


class _GatedStub:
    """Shared attribute + method surface for all gated stubs.

    Subclasses override the class-level attribute block — the
    ``.build()`` / ``.preprocess()`` / ``.embed()`` plumbing is
    inherited and always routes through :class:`GatedAccessError`.
    """

    id: str = "gated_stub"
    display_name: str = "Gated stub"
    gated: bool = True
    hf_repo: str | None = None
    input_size: tuple[int, int] = (224, 224)
    embedding_dim: int = 1024
    tier_compatibility: frozenset[str] = frozenset({"T2", "T3"})
    vram_gb: float = 4.0
    license: str = "CC-BY-NC-4.0"
    citation: str = ""

    def build(self, pretrained: bool = True) -> Any:
        raise GatedAccessError(
            f"{self.id!r} adapter is a Phase 13 stub — it registers "
            f"metadata + advertises HF repo {self.hf_repo!r} but has no "
            "real build path yet. The fallback resolver will swap this "
            "request for DINOv2; a real adapter lands when a user "
            "explicitly needs this backbone."
        )

    def preprocess(self, image: Any) -> Any:
        from openpathai.foundation.dinov2 import DINOv2SmallAdapter

        return DINOv2SmallAdapter().preprocess(image)

    def embed(self, images: Any) -> np.ndarray:
        # embed() is only reachable after a successful build(); for
        # stubs that's never, but the method is required by the
        # FoundationAdapter protocol so we raise the same error.
        raise GatedAccessError(
            f"{self.id!r} is a stub adapter; no real embed path. "
            "Use the FallbackDecision-resolved backbone instead."
        )


class UNI2HStub(_GatedStub):
    id = "uni2_h"
    display_name = "UNI2-h ViT-H/14 (MahmoodLab)"
    hf_repo = "MahmoodLab/UNI2-h"
    embedding_dim = 1536
    vram_gb = 10.0
    citation = "Chen et al., 'UNI2-h: scaling pathology foundation models' (MahmoodLab, 2024)."


class CONCHStub(_GatedStub):
    id = "conch"
    display_name = "CONCH (MahmoodLab, Mahmood Lab)"
    hf_repo = "MahmoodLab/CONCH"
    embedding_dim = 512
    vram_gb = 3.0
    citation = (
        "Lu et al., 'A visual-language foundation model for "
        "computational pathology' (Nature Medicine, 2024)."
    )


class Virchow2Stub(_GatedStub):
    id = "virchow2"
    display_name = "Virchow2 ViT-H/14 (Paige AI)"
    hf_repo = "paige-ai/Virchow2"
    embedding_dim = 1280
    vram_gb = 10.0
    citation = (
        "Zimmermann et al., 'Virchow2: Scaling Self-Supervised "
        "Mixed-Magnification Models in Pathology' (2024)."
    )


class ProvGigaPathStub(_GatedStub):
    id = "prov_gigapath"
    display_name = "Prov-GigaPath (Microsoft)"
    hf_repo = "prov-gigapath/prov-gigapath"
    embedding_dim = 1536
    vram_gb = 12.0
    citation = (
        "Xu et al., 'A whole-slide foundation model for digital "
        "pathology from real-world data' (Nature, 2024)."
    )


class HibouStub(_GatedStub):
    id = "hibou"
    display_name = "Hibou ViT-B/14 (HistAI)"
    hf_repo = "histai/hibou-B"
    embedding_dim = 768
    vram_gb = 3.0
    license = "Apache-2.0"
    citation = "HistAI, 'Hibou: A Family of Foundational Vision Transformers for Pathology' (2024)."
