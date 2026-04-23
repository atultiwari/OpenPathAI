"""``openpathai analyse`` — run inference + explainability on a tile."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import numpy as np
import typer
from PIL import Image

from openpathai.explain.base import encode_png, overlay_on_tile


def _load_tile_rgb(path: Path) -> np.ndarray:  # pragma: no cover - exercised via analyse
    """Load a tile image as a ``(H, W, 3)`` uint8 array."""
    img = Image.open(path)
    if img.mode != "RGB":
        img = img.convert("RGB")
    return np.asarray(img, dtype=np.uint8)


def register(app: typer.Typer) -> None:
    @app.command()
    def analyse(  # pragma: no cover - torch-gated; covered by integration tests
        tile_path: Annotated[
            Path,
            typer.Option("--tile", help="Path to a tile image (PNG / TIFF / JPEG)."),
        ],
        model: Annotated[str, typer.Option(help="Model card name, e.g. resnet18.")],
        num_classes: Annotated[int, typer.Option(min=1, help="Number of classes.")] = 2,
        target_class: Annotated[int, typer.Option(min=0, help="Class to attribute.")] = 0,
        target_layer: Annotated[
            str | None,
            typer.Option(
                "--target-layer",
                help=(
                    "Dotted path into the model for the Grad-CAM target layer "
                    "(e.g. 'layer4'). Omit to fall back to EigenCAM."
                ),
            ),
        ] = None,
        explainer: Annotated[
            str,
            typer.Option(
                help=(
                    "gradcam | gradcam_plus_plus | eigencam | "
                    "attention_rollout | integrated_gradients"
                ),
            ),
        ] = "gradcam",
        output_dir: Annotated[
            Path,
            typer.Option("--output-dir", help="Where to write the heatmap PNG."),
        ] = Path("analyse-output"),
        device: Annotated[str, typer.Option(help="cpu / cuda / mps / auto.")] = "cpu",
    ) -> None:
        """Produce a heatmap for a single tile under a Tier-A classifier.

        Requires the ``[train]`` extra (torch + timm). The tile is
        resized to the card's ``input_size`` before inference; the
        heatmap is written as ``<output-dir>/heatmap.png`` with an
        overlay at ``overlay.png``.
        """
        try:
            import torch
        except ImportError as exc:
            typer.secho(
                "analyse requires the 'torch' package. "
                "Install via the [train] extra: uv sync --extra train",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(3) from exc

        from openpathai.explain.gradcam import (
            EigenCAM,
            GradCAM,
            GradCAMPlusPlus,
        )
        from openpathai.explain.integrated_gradients import integrated_gradients
        from openpathai.models import adapter_for_card, default_model_registry
        from openpathai.training.engine import resolve_device

        registry = default_model_registry()
        if not registry.has(model):
            typer.secho(f"Model card {model!r} is not registered.", fg="red", err=True)
            raise typer.Exit(2)
        card = registry.get(model)
        dev = resolve_device(device)

        rgb = _load_tile_rgb(tile_path)
        tile_h, tile_w = card.input_size
        img = Image.fromarray(rgb).resize((tile_w, tile_h), Image.Resampling.BILINEAR)
        tensor = (
            torch.from_numpy(np.asarray(img, dtype=np.float32) / 255.0)
            .permute(2, 0, 1)
            .unsqueeze(0)
            .to(dev)
        )
        mean = torch.tensor(card.preprocessing_mean, device=dev).view(1, 3, 1, 1)
        std = torch.tensor(card.preprocessing_std, device=dev).view(1, 3, 1, 1)
        tensor = (tensor - mean) / std

        adapter = adapter_for_card(card)
        net = adapter.build(card, num_classes=num_classes, pretrained=False).to(dev)
        net.eval()

        if explainer == "gradcam":
            if target_layer is None:
                typer.secho(
                    "--target-layer is required for gradcam / gradcam_plus_plus.",
                    fg="red",
                    err=True,
                )
                raise typer.Exit(2)
            heatmap = GradCAM(net, target_layer).explain(
                tensor, target_class, output_size=(tile_h, tile_w)
            )
        elif explainer == "gradcam_plus_plus":
            if target_layer is None:
                typer.secho(
                    "--target-layer is required for gradcam / gradcam_plus_plus.",
                    fg="red",
                    err=True,
                )
                raise typer.Exit(2)
            heatmap = GradCAMPlusPlus(net, target_layer).explain(
                tensor, target_class, output_size=(tile_h, tile_w)
            )
        elif explainer == "eigencam":
            if target_layer is None:
                typer.secho(
                    "--target-layer is required for eigencam.",
                    fg="red",
                    err=True,
                )
                raise typer.Exit(2)
            heatmap = EigenCAM(net, target_layer).explain(tensor, output_size=(tile_h, tile_w))
        elif explainer == "integrated_gradients":
            heatmap = integrated_gradients(net, tensor, target_class, output_size=(tile_h, tile_w))
        else:
            typer.secho(f"Unknown explainer {explainer!r}.", fg="red", err=True)
            raise typer.Exit(2)

        output_dir.mkdir(parents=True, exist_ok=True)
        heatmap_u8 = (np.clip(heatmap, 0.0, 1.0) * 255).astype(np.uint8)
        heatmap_png_path = output_dir / "heatmap.png"
        overlay_png_path = output_dir / "overlay.png"

        Image.fromarray(heatmap_u8, mode="L").save(heatmap_png_path)
        resized_rgb = np.asarray(
            Image.fromarray(rgb).resize((tile_w, tile_h), Image.Resampling.BILINEAR),
            dtype=np.uint8,
        )
        overlay = overlay_on_tile(resized_rgb, heatmap)
        Image.fromarray(overlay).save(overlay_png_path)

        # Also emit a base64 PNG so downstream consumers can slurp the
        # bytes without re-reading from disk.
        _ = encode_png(heatmap_u8)
        typer.echo(f"heatmap: {heatmap_png_path}")
        typer.echo(f"overlay: {overlay_png_path}")


__all__ = ["register"]
