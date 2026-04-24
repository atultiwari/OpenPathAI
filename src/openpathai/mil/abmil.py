"""Attention-based MIL (Ilse et al., 2018).

A gated-attention aggregator: the attention score for tile ``i`` is

    a_i = softmax(V · tanh(U · x_i) ⊙ sigmoid(W · x_i))

and the bag representation is ``sum(a_i · x_i)``, then a linear
classifier on top. Pure torch, CPU-fast, ~60 LOC.
"""

from __future__ import annotations

from typing import Any, cast

import numpy as np

from openpathai.mil.adapter import MILForwardOutput, MILTrainingReport

__all__ = ["ABMILAdapter"]


class ABMILAdapter:
    """Gated attention-based MIL (Ilse et al. 2018)."""

    id: str = "abmil"

    def __init__(
        self,
        *,
        embedding_dim: int,
        num_classes: int,
        hidden_dim: int = 128,
    ) -> None:
        self.embedding_dim = embedding_dim
        self.num_classes = num_classes
        self._hidden_dim = hidden_dim
        self._module: Any = None

    # ─── Build / train / forward ──────────────────────────────────

    def _build(self, seed: int) -> Any:
        import torch
        import torch.nn as nn

        torch.manual_seed(seed)

        class _ABMIL(nn.Module):
            def __init__(self, embedding_dim: int, hidden_dim: int, num_classes: int) -> None:
                super().__init__()
                self.U = nn.Linear(embedding_dim, hidden_dim)
                self.W = nn.Linear(embedding_dim, hidden_dim)
                self.V = nn.Linear(hidden_dim, 1)
                self.classifier = nn.Linear(embedding_dim, num_classes)

            def forward(self, bag: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
                # bag: (N, D)
                h_u = torch.tanh(self.U(bag))
                h_w = torch.sigmoid(self.W(bag))
                gated = h_u * h_w
                attn_logits = self.V(gated).squeeze(-1)  # (N,)
                attn = torch.softmax(attn_logits, dim=0)
                bag_vec = (attn.unsqueeze(-1) * bag).sum(dim=0)  # (D,)
                logits = self.classifier(bag_vec)  # (num_classes,)
                return logits, attn

        return _ABMIL(self.embedding_dim, self._hidden_dim, self.num_classes)

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
            raise ValueError(f"bags ({len(bags)}) and labels ({len(labels)}) must be same length")
        if epochs < 1:
            raise ValueError(f"epochs must be >= 1; got {epochs}")

        self._module = self._build(seed)
        optim = torch.optim.Adam(self._module.parameters(), lr=lr)
        losses: list[float] = []
        labels_tensor = torch.as_tensor(np.asarray(labels, dtype=np.int64))

        for _ in range(epochs):
            epoch_losses: list[float] = []
            for bag, label in zip(bags, labels_tensor, strict=True):
                bag_tensor = torch.as_tensor(np.asarray(bag, dtype=np.float32))
                if bag_tensor.ndim != 2:
                    raise ValueError(f"bag must be 2-D (N, D); got {bag_tensor.shape}")
                optim.zero_grad()
                logits, _attn = self._module(bag_tensor)
                loss = F.cross_entropy(logits.unsqueeze(0), label.unsqueeze(0))
                loss.backward()
                optim.step()
                epoch_losses.append(float(loss.detach()))
            losses.append(float(np.mean(epoch_losses)))

        final_loss = losses[-1] if losses else 0.0
        return MILTrainingReport(
            aggregator_id=self.id,
            num_classes=self.num_classes,
            embedding_dim=self.embedding_dim,
            n_bags_train=len(bags),
            epochs_run=epochs,
            final_train_loss=final_loss,
            train_loss_curve=tuple(losses),
        )

    def forward(self, bag: Any) -> MILForwardOutput:
        import torch

        if self._module is None:
            raise RuntimeError("call fit() before forward()")
        self._module.eval()
        bag_tensor = torch.as_tensor(np.asarray(bag, dtype=np.float32))
        with torch.no_grad():
            logits, attn = self._module(bag_tensor)
        return MILForwardOutput(
            logits=logits.detach().cpu().numpy().astype(np.float32),
            attention=attn.detach().cpu().numpy().astype(np.float32),
        )

    def slide_heatmap(self, bag: Any, coords: Any) -> np.ndarray:
        out = self.forward(bag)
        coords_arr = np.asarray(coords)
        if coords_arr.ndim != 2 or coords_arr.shape[1] != 2:
            raise ValueError(f"coords must be (N, 2); got shape {coords_arr.shape}")
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
