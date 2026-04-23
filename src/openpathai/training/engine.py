"""Supervised training engine — Tier A (Phase 3).

The engine is intentionally small but Lightning-compatible:

* :class:`TileClassifierModule` is an ``nn.Module`` shaped like a
  Lightning ``LightningModule`` (``training_step`` / ``validation_step``
  methods). When the optional ``lightning`` dependency is installed, a
  later phase can drop this module directly into ``lightning.Trainer``
  without changing the model code.
* :class:`LightningTrainer` drives a plain-torch training loop with
  deterministic seeding, AMP toggle, and validation after every epoch.
  It lazy-imports torch so the module is importable without the
  ``[train]`` extra.

All public entry points accept a :class:`TrainingConfig` + a pair of
:class:`openpathai.training.datasets.InMemoryTileBatch` (train + val)
and return a :class:`TrainingReportArtifact`.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from openpathai.models.adapter import adapter_for_card
from openpathai.models.cards import ModelCard
from openpathai.training.artifacts import EpochRecord, TrainingReportArtifact
from openpathai.training.calibration import TemperatureScaler
from openpathai.training.config import LossConfig, TrainingConfig
from openpathai.training.datasets import InMemoryTileBatch, build_torch_dataset
from openpathai.training.metrics import accuracy, expected_calibration_error, macro_f1

if TYPE_CHECKING:  # pragma: no cover - type hints only
    import torch

log = logging.getLogger(__name__)

__all__ = [
    "LightningTrainer",
    "TileClassifierModule",
    "resolve_device",
]


def resolve_device(preferred: str) -> str:
    """Resolve ``auto`` to ``cuda`` / ``mps`` / ``cpu`` based on runtime."""
    if preferred != "auto":
        return preferred
    try:  # pragma: no cover - torch-gated
        import torch
    except ImportError:  # pragma: no cover - handled by caller
        return "cpu"
    if torch.cuda.is_available():  # pragma: no cover
        return "cuda"
    if (  # pragma: no cover
        getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available()
    ):
        return "mps"
    return "cpu"  # pragma: no cover


def _build_loss_fn(loss_cfg: LossConfig, *, num_classes: int) -> Any:  # pragma: no cover
    """Return a closure ``fn(logits, targets) -> scalar`` using torch.

    Torch-gated — covered by the integration test when the ``[train]``
    extra is installed; excluded from coverage otherwise.
    """
    import torch
    import torch.nn.functional as F

    class_weights = (
        torch.tensor(loss_cfg.class_weights, dtype=torch.float32)
        if loss_cfg.class_weights is not None
        else None
    )
    class_counts = (
        torch.tensor(loss_cfg.class_counts, dtype=torch.float32)
        if loss_cfg.class_counts is not None
        else None
    )

    if loss_cfg.kind in {"cross_entropy", "weighted_cross_entropy"}:

        def _ce(logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
            weight = class_weights.to(logits.device) if class_weights is not None else None
            return F.cross_entropy(
                logits,
                targets,
                weight=weight,
                label_smoothing=loss_cfg.label_smoothing,
            )

        return _ce

    if loss_cfg.kind == "focal":
        gamma = loss_cfg.focal_gamma
        alpha = loss_cfg.focal_alpha

        def _focal(logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
            log_probs = F.log_softmax(logits, dim=-1)
            probs = log_probs.exp()
            idx = torch.arange(len(targets), device=logits.device)
            log_pt = log_probs[idx, targets]
            pt = probs[idx, targets]
            modulator = (1.0 - pt).pow(gamma)
            per_example = -modulator * log_pt
            if alpha is not None:
                per_example = per_example * alpha
            return per_example.mean()

        return _focal

    if loss_cfg.kind == "ldam":
        if class_counts is None:
            raise ValueError("LDAM requires loss.class_counts to be set")
        raw_margins = 1.0 / class_counts.pow(0.25)
        margins = raw_margins * (loss_cfg.ldam_max_m / float(raw_margins.max().item()))
        scale = loss_cfg.ldam_scale

        def _ldam(logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
            m = margins.to(logits.device)
            offsets = torch.zeros_like(logits)
            offsets[torch.arange(len(targets)), targets] = m[targets]
            adjusted = (logits - offsets) * scale
            weight = class_weights.to(logits.device) if class_weights is not None else None
            return F.cross_entropy(adjusted, targets, weight=weight)

        return _ldam

    raise ValueError(f"Unknown loss kind {loss_cfg.kind!r}")


def _build_optimizer(cfg: TrainingConfig, parameters: Any) -> Any:  # pragma: no cover
    import torch

    opt = cfg.optimizer
    if opt.kind == "sgd":
        return torch.optim.SGD(
            parameters,
            lr=opt.lr,
            momentum=opt.momentum,
            weight_decay=opt.weight_decay,
        )
    if opt.kind == "adam":
        return torch.optim.Adam(parameters, lr=opt.lr, weight_decay=opt.weight_decay)
    if opt.kind == "adamw":
        return torch.optim.AdamW(parameters, lr=opt.lr, weight_decay=opt.weight_decay)
    raise ValueError(f"Unknown optimizer kind {opt.kind!r}")


def _build_scheduler(cfg: TrainingConfig, optimizer: Any) -> Any:  # pragma: no cover
    import torch

    sched = cfg.scheduler
    if sched.kind == "none":
        return None
    if sched.kind == "cosine":
        t_max = sched.t_max or cfg.epochs
        return torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=t_max)
    if sched.kind == "step":
        if sched.step_size is None:
            raise ValueError("scheduler.step_size must be set for kind='step'")
        return torch.optim.lr_scheduler.StepLR(
            optimizer,
            step_size=sched.step_size,
            gamma=sched.gamma,
        )
    raise ValueError(f"Unknown scheduler kind {sched.kind!r}")


class TileClassifierModule:
    """A Lightning-shaped module with a backbone + loss.

    Storing ``model`` and ``loss_fn`` on the instance keeps the
    training loop trivially substitutable for ``lightning.Trainer``
    when the optional Lightning dependency is available: subclass this
    and mix in ``lightning.LightningModule`` to plug straight in.
    """

    def __init__(
        self,
        *,
        backbone: Any,
        loss_fn: Any,
    ) -> None:
        self.model = backbone
        self.loss_fn = loss_fn

    def training_step(self, batch: tuple[Any, Any]) -> Any:
        x, y = batch
        logits = self.model(x)
        return self.loss_fn(logits, y)

    def validation_step(self, batch: tuple[Any, Any]) -> Any:  # pragma: no cover
        import torch

        x, y = batch
        with torch.no_grad():
            logits = self.model(x)
            loss = self.loss_fn(logits, y)
        return logits.detach(), y.detach(), loss.detach()


@dataclass
class _LoopState:
    step: int = 0


class LightningTrainer:
    """Phase 3 supervised trainer.

    The class is deliberately small: construct with a
    :class:`TrainingConfig`, call :meth:`fit` with a model card and a
    pair of :class:`InMemoryTileBatch` (train + val), receive a
    :class:`TrainingReportArtifact`.

    Delegates the actual model instantiation to
    :func:`openpathai.models.adapter.adapter_for_card`, so swapping the
    backbone is just a matter of pointing at a different card.
    """

    def __init__(
        self,
        config: TrainingConfig,
        *,
        card: ModelCard,
        checkpoint_dir: str | Path | None = None,
    ) -> None:
        self.config = config
        self.card = card
        self.checkpoint_dir = Path(checkpoint_dir) if checkpoint_dir is not None else None
        if self.card.name != self.config.model_card:
            raise ValueError(
                f"config.model_card={self.config.model_card!r} does not match "
                f"card.name={self.card.name!r}"
            )

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def fit(  # pragma: no cover
        self,
        *,
        train: InMemoryTileBatch,
        val: InMemoryTileBatch | None = None,
    ) -> TrainingReportArtifact:
        try:
            import torch
            from torch.utils.data import DataLoader
        except ImportError as exc:  # pragma: no cover - exercised when torch missing
            raise ImportError(
                "Training requires the 'torch' package. "
                "Install it via the [train] extra: `uv sync --extra train`."
            ) from exc

        torch.manual_seed(self.config.seed)
        np.random.seed(self.config.seed)

        device = resolve_device(self.config.device)
        log.info("LightningTrainer: device=%s", device)

        adapter = adapter_for_card(self.card)
        backbone = adapter.build(
            self.card,
            num_classes=self.config.num_classes,
            pretrained=self.config.pretrained,
        ).to(device)
        loss_fn = _build_loss_fn(self.config.loss, num_classes=self.config.num_classes)
        module = TileClassifierModule(backbone=backbone, loss_fn=loss_fn)
        optimizer = _build_optimizer(self.config, backbone.parameters())
        scheduler = _build_scheduler(self.config, optimizer)

        train_loader = DataLoader(
            build_torch_dataset(train),
            batch_size=self.config.batch_size,
            shuffle=True,
            num_workers=self.config.num_workers,
            drop_last=False,
        )
        val_loader = (
            DataLoader(
                build_torch_dataset(val),
                batch_size=self.config.batch_size,
                shuffle=False,
                num_workers=self.config.num_workers,
                drop_last=False,
            )
            if val is not None
            else None
        )

        history: list[EpochRecord] = []
        final_val_logits: np.ndarray | None = None
        final_val_targets: np.ndarray | None = None

        for epoch in range(self.config.epochs):
            backbone.train()
            train_losses: list[float] = []
            for batch in train_loader:
                x, y = batch
                x = x.to(device)
                y = y.to(device)
                optimizer.zero_grad()
                loss = module.training_step((x, y))
                loss.backward()
                optimizer.step()
                train_losses.append(float(loss.detach().cpu().item()))
            if scheduler is not None:
                scheduler.step()

            train_loss = float(np.mean(train_losses)) if train_losses else float("nan")
            record = EpochRecord(epoch=epoch, train_loss=train_loss)

            if val_loader is not None:
                val_metrics, all_logits, all_targets = self._validate(
                    module,
                    val_loader,
                    device=device,
                    num_classes=self.config.num_classes,
                )
                record = EpochRecord(
                    epoch=epoch,
                    train_loss=train_loss,
                    val_loss=val_metrics["loss"],
                    val_accuracy=val_metrics["accuracy"],
                    val_macro_f1=val_metrics["macro_f1"],
                    val_ece=val_metrics["ece"],
                )
                final_val_logits = all_logits
                final_val_targets = all_targets
            history.append(record)
            log.info("epoch=%d %s", epoch, record.model_dump())

        checkpoint_path = self._save_checkpoint(backbone)

        temperature: float | None = None
        ece_after: float | None = None
        ece_before = history[-1].val_ece if history else None
        if self.config.calibrate and final_val_logits is not None and final_val_targets is not None:
            scaler = TemperatureScaler().fit(final_val_logits, final_val_targets)
            temperature = scaler.temperature
            scaled_probs = _softmax(scaler.transform(final_val_logits))
            ece_after = expected_calibration_error(scaled_probs, final_val_targets)

        final = history[-1] if history else EpochRecord(epoch=0, train_loss=float("nan"))
        return TrainingReportArtifact(
            model_card=self.card.name,
            num_classes=self.config.num_classes,
            epochs=self.config.epochs,
            seed=self.config.seed,
            device=device,
            checkpoint_path=str(checkpoint_path) if checkpoint_path else None,
            final_train_loss=final.train_loss,
            final_val_loss=final.val_loss,
            final_val_accuracy=final.val_accuracy,
            final_val_macro_f1=final.val_macro_f1,
            ece_before_calibration=ece_before,
            ece_after_calibration=ece_after,
            temperature=temperature,
            class_names=train.class_names,
            history=tuple(history),
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _validate(  # pragma: no cover
        module: TileClassifierModule,
        loader: Any,
        *,
        device: str,
        num_classes: int,
    ) -> tuple[dict[str, float], np.ndarray, np.ndarray]:
        import torch

        module.model.eval()
        losses: list[float] = []
        all_logits: list[np.ndarray] = []
        all_targets: list[np.ndarray] = []
        with torch.no_grad():
            for batch in loader:
                x, y = batch
                x = x.to(device)
                y = y.to(device)
                logits, targets, loss = module.validation_step((x, y))
                losses.append(float(loss.cpu().item()))
                all_logits.append(logits.cpu().numpy())
                all_targets.append(targets.cpu().numpy())
        logits_np = np.concatenate(all_logits) if all_logits else np.zeros((0, num_classes))
        targets_np = (
            np.concatenate(all_targets).astype(np.int64)
            if all_targets
            else np.zeros((0,), dtype=np.int64)
        )
        preds = np.argmax(logits_np, axis=-1) if logits_np.size else np.zeros((0,), dtype=np.int64)
        probs = _softmax(logits_np) if logits_np.size else logits_np
        return (
            {
                "loss": float(np.mean(losses)) if losses else float("nan"),
                "accuracy": accuracy(targets_np, preds) if len(targets_np) else 0.0,
                "macro_f1": macro_f1(targets_np, preds, num_classes) if len(targets_np) else 0.0,
                "ece": (expected_calibration_error(probs, targets_np) if logits_np.size else 0.0),
            },
            logits_np,
            targets_np,
        )

    def _save_checkpoint(self, model: Any) -> Path | None:  # pragma: no cover
        if self.checkpoint_dir is None:
            return None
        import torch

        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        # Content-hash the state dict so the filename is deterministic.
        state_dict = model.state_dict()
        hasher = hashlib.sha256()
        for key in sorted(state_dict):
            hasher.update(key.encode("utf-8"))
            tensor = state_dict[key].detach().cpu().contiguous()
            hasher.update(tensor.numpy().tobytes())
        digest = hasher.hexdigest()[:16]
        path = self.checkpoint_dir / f"{self.card.name}-{digest}.pt"
        torch.save(state_dict, path)
        return path


def _softmax(logits: np.ndarray) -> np.ndarray:  # pragma: no cover
    shifted = logits - np.max(logits, axis=-1, keepdims=True)
    exp = np.exp(shifted)
    return exp / np.sum(exp, axis=-1, keepdims=True)
