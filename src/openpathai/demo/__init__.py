"""Trivial demo nodes used by docs, the quick-start notebook, and the
``pipelines/supervised_synthetic.yaml`` smoke test.

These exist so a user can run ``openpathai run <yaml>`` and observe the
pipeline-executor / content-addressable-cache machinery end-to-end
without installing torch or downloading any dataset. Every node is
deliberately tiny — real pipelines ride the Phase 3 / 4 / 9 nodes.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from openpathai.pipeline.node import node
from openpathai.pipeline.schema import FloatArtifact, IntArtifact

__all__ = [
    "ConstantInput",
    "DoubleInput",
    "MeanInput",
]


class ConstantInput(BaseModel):
    """Input model for :func:`constant_int`."""

    model_config = ConfigDict(extra="forbid")

    value: int


class DoubleInput(BaseModel):
    """Input model for :func:`double_int`."""

    model_config = ConfigDict(extra="forbid")

    value: int


class MeanInput(BaseModel):
    """Input model for :func:`mean_int_pair`."""

    model_config = ConfigDict(extra="forbid")

    a: int
    b: int


@node(
    id="demo.constant",
    label="Constant integer",
    tooltip="Emits a constant int — the smallest possible pipeline source node.",
)
def constant_int(cfg: ConstantInput) -> IntArtifact:
    return IntArtifact(value=cfg.value)


@node(
    id="demo.double",
    label="Double an integer",
    tooltip="Doubles its input int. Useful for smoke-testing reference resolution.",
)
def double_int(cfg: DoubleInput) -> IntArtifact:
    return IntArtifact(value=cfg.value * 2)


@node(
    id="demo.mean",
    label="Mean of two integers (as float)",
    tooltip="Averages two ints into a FloatArtifact — demonstrates cross-type downstream fields.",
)
def mean_int_pair(cfg: MeanInput) -> FloatArtifact:
    return FloatArtifact(value=(cfg.a + cfg.b) / 2.0)
