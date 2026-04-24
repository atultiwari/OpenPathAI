"""CLAM — Clustering-constrained Attention MIL (Lu et al., 2021).

Single-branch variant shipped in Phase 13: same attention as ABMIL
plus an instance-level clustering loss that pushes high-attention
tiles toward the bag label and low-attention tiles away.

Multi-branch CLAM, TransMIL, DSMIL register as stubs that raise
:class:`NotImplementedError` with a pointer to the Phase 13 worklog;
promotion to real adapters is a Phase 13.5 micro-phase.
"""

from __future__ import annotations

from typing import Any, cast

import numpy as np

from openpathai.mil.adapter import MILForwardOutput, MILTrainingReport

__all__ = [
    "CLAMMultiBranchStub",
    "CLAMSingleBranchAdapter",
    "DSMILStub",
    "TransMILStub",
]


class CLAMSingleBranchAdapter:
    """CLAM-SB: attention + instance-level clustering loss."""

    id: str = "clam_sb"

    def __init__(
        self,
        *,
        embedding_dim: int,
        num_classes: int,
        hidden_dim: int = 128,
        instance_loss_weight: float = 0.3,
        top_k: int = 8,
    ) -> None:
        self.embedding_dim = embedding_dim
        self.num_classes = num_classes
        self._hidden_dim = hidden_dim
        self._instance_loss_weight = instance_loss_weight
        self._top_k = top_k
        self._module: Any = None

    def _build(self, seed: int) -> Any:
        import torch
        import torch.nn as nn

        torch.manual_seed(seed)

        class _ClamSB(nn.Module):
            def __init__(self, embedding_dim: int, hidden_dim: int, num_classes: int) -> None:
                super().__init__()
                self.U = nn.Linear(embedding_dim, hidden_dim)
                self.W = nn.Linear(embedding_dim, hidden_dim)
                self.V = nn.Linear(hidden_dim, 1)
                self.classifier = nn.Linear(embedding_dim, num_classes)
                # Instance-level clustering head: binary (in-class / out-of-class).
                self.instance_head = nn.Linear(embedding_dim, 2)

            def forward(self, bag: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
                h_u = torch.tanh(self.U(bag))
                h_w = torch.sigmoid(self.W(bag))
                attn_logits = self.V(h_u * h_w).squeeze(-1)
                attn = torch.softmax(attn_logits, dim=0)
                bag_vec = (attn.unsqueeze(-1) * bag).sum(dim=0)
                bag_logits = self.classifier(bag_vec)
                inst_logits = self.instance_head(bag)  # (N, 2)
                return bag_logits, attn, inst_logits

        return _ClamSB(self.embedding_dim, self._hidden_dim, self.num_classes)

    def fit(
        self,
        bags: list[Any],
        labels: Any,
        *,
        epochs: int = 5,
        lr: float = 1e-3,
        seed: int = 1234,
    ) -> MILTrainingReport:
        import torch
        from torch.nn import functional as F

        if len(bags) != len(labels):
            raise ValueError("bags and labels must be same length")
        if epochs < 1:
            raise ValueError(f"epochs must be >= 1; got {epochs}")

        self._module = self._build(seed)
        optim = torch.optim.Adam(self._module.parameters(), lr=lr)
        labels_tensor = torch.as_tensor(np.asarray(labels, dtype=np.int64))
        losses: list[float] = []

        for _ in range(epochs):
            epoch_losses: list[float] = []
            for bag, label in zip(bags, labels_tensor, strict=True):
                bag_tensor = torch.as_tensor(np.asarray(bag, dtype=np.float32))
                optim.zero_grad()
                bag_logits, attn, inst_logits = self._module(bag_tensor)
                bag_loss = F.cross_entropy(bag_logits.unsqueeze(0), label.unsqueeze(0))
                # Instance-level pseudo-labels from top-k / bottom-k attention.
                k = min(self._top_k, bag_tensor.shape[0])
                top_idx = torch.topk(attn, k=k).indices
                bot_idx = torch.topk(-attn, k=k).indices
                inst_targets = torch.zeros(bag_tensor.shape[0], dtype=torch.long)
                inst_targets[top_idx] = 1  # "in-class" pseudo-label
                inst_targets[bot_idx] = 0
                inst_loss = F.cross_entropy(inst_logits, inst_targets)
                loss = bag_loss + self._instance_loss_weight * inst_loss
                loss.backward()
                optim.step()
                epoch_losses.append(float(loss.detach()))
            losses.append(float(np.mean(epoch_losses)))

        return MILTrainingReport(
            aggregator_id=self.id,
            num_classes=self.num_classes,
            embedding_dim=self.embedding_dim,
            n_bags_train=len(bags),
            epochs_run=epochs,
            final_train_loss=losses[-1] if losses else 0.0,
            train_loss_curve=tuple(losses),
        )

    def forward(self, bag: Any) -> MILForwardOutput:
        import torch

        if self._module is None:
            raise RuntimeError("call fit() before forward()")
        self._module.eval()
        bag_tensor = torch.as_tensor(np.asarray(bag, dtype=np.float32))
        with torch.no_grad():
            bag_logits, attn, _ = self._module(bag_tensor)
        return MILForwardOutput(
            logits=bag_logits.detach().cpu().numpy().astype(np.float32),
            attention=attn.detach().cpu().numpy().astype(np.float32),
        )

    def slide_heatmap(self, bag: Any, coords: Any) -> np.ndarray:
        out = self.forward(bag)
        coords_arr = np.asarray(coords)
        if coords_arr.ndim != 2 or coords_arr.shape[1] != 2:
            raise ValueError(f"coords must be (N, 2); got {coords_arr.shape}")
        if coords_arr.shape[0] != out.attention.shape[0]:
            raise ValueError(
                f"coords rows ({coords_arr.shape[0]}) and bag size "
                f"({out.attention.shape[0]}) must match"
            )
        y_max = int(coords_arr[:, 0].max()) + 1
        x_max = int(coords_arr[:, 1].max()) + 1
        heatmap = np.zeros((y_max, x_max), dtype=np.float32)
        for (y, x), value in zip(coords_arr, out.attention, strict=True):
            heatmap[int(y), int(x)] = float(value)
        return cast(np.ndarray, heatmap)


class _MILStub:
    """Shared stub base for non-shipped aggregators."""

    id: str = "mil_stub"
    embedding_dim: int = 0
    num_classes: int = 0
    _promotion_note: str = ""

    def __init__(self, *, embedding_dim: int, num_classes: int) -> None:
        self.embedding_dim = embedding_dim
        self.num_classes = num_classes

    def _raise(self, method: str) -> None:
        raise NotImplementedError(
            f"{type(self).__name__}.{method} is a Phase 13 stub — the "
            "aggregator is registered so `openpathai mil list` shows "
            "it, but the implementation lands in a Phase 13.5 micro-"
            f"phase when a user asks. {self._promotion_note}"
        )

    def forward(self, bag: Any) -> MILForwardOutput:
        self._raise("forward")
        raise AssertionError("unreachable")  # pragma: no cover

    def fit(
        self,
        bags: list[Any],
        labels: Any,
        *,
        epochs: int = 5,
        lr: float = 1e-3,
        seed: int = 1234,
    ) -> MILTrainingReport:
        self._raise("fit")
        raise AssertionError("unreachable")  # pragma: no cover

    def slide_heatmap(self, bag: Any, coords: Any) -> np.ndarray:
        self._raise("slide_heatmap")
        raise AssertionError("unreachable")  # pragma: no cover


class CLAMMultiBranchStub(_MILStub):
    id = "clam_mb"
    _promotion_note = "Multi-branch CLAM requires a per-class attention head set."


class TransMILStub(_MILStub):
    id = "transmil"
    _promotion_note = "TransMIL requires Nyström-attention + Morpheus transformer blocks."


class DSMILStub(_MILStub):
    id = "dsmil"
    _promotion_note = "DSMIL requires dual-stream max-attention + critic branches."
