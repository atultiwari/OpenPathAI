"""Artifacts produced by the models layer.

Phase 3 ships one artifact type: :class:`ModelArtifact`, which captures
the identity of a built model (card name, number of classes, adapter id,
and — when materialised — a state-dict hash) so downstream pipeline
steps can depend on "this exact model" by content hash.
"""

from __future__ import annotations

from openpathai.pipeline.schema import Artifact

__all__ = ["ModelArtifact"]


class ModelArtifact(Artifact):
    """Identity of a built model.

    ``state_dict_hash`` is optional because some callers just want to
    record the card+num-classes tuple (for planning) before the weights
    are actually materialised.
    """

    card_name: str
    num_classes: int
    adapter: str
    pretrained: bool = True
    state_dict_hash: str | None = None
