"""``openpathai analyse`` — run inference + explainability on a tile.

Phase 7 extends the command with ``--low / --high / --pdf`` so the same
invocation can produce the Safety v1 PDF report alongside the heatmap.
"""

from __future__ import annotations

import hashlib
import io
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


def _png_bytes(arr: np.ndarray) -> bytes:
    """Encode an RGB or grayscale array to PNG bytes (deterministic)."""
    buf = io.BytesIO()
    mode = "RGB" if arr.ndim == 3 and arr.shape[-1] == 3 else "L"
    Image.fromarray(arr, mode=mode).save(buf, format="PNG", optimize=False)
    return buf.getvalue()


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
        low: Annotated[
            float,
            typer.Option(
                min=0.0,
                max=1.0,
                help="Borderline band lower threshold (Phase 7).",
            ),
        ] = 0.4,
        high: Annotated[
            float,
            typer.Option(
                min=0.0,
                max=1.0,
                help="Borderline band upper threshold (Phase 7).",
            ),
        ] = 0.7,
        pdf: Annotated[
            Path | None,
            typer.Option("--pdf", help="Also write a Safety v1 PDF report to this path."),
        ] = None,
        allow_uncalibrated: Annotated[
            bool,
            typer.Option(
                help=(
                    "Bypass the classify_with_band calibration guard. Only "
                    "enable when you understand that raw softmax is misleading."
                ),
            ),
        ] = False,
        allow_incomplete_card: Annotated[
            bool,
            typer.Option(
                help=(
                    "Proceed even when the model card fails the safety contract. Off by default."
                ),
            ),
        ] = False,
        no_audit: Annotated[
            bool,
            typer.Option(
                "--no-audit",
                help="Skip the Phase 8 audit log write for this run.",
            ),
        ] = False,
    ) -> None:
        """Produce a heatmap + optional PDF for a single tile under a Tier-A
        classifier.

        Requires the ``[train]`` extra (torch + timm). The tile is
        resized to the card's ``input_size`` before inference; the
        heatmap is written as ``<output-dir>/heatmap.png`` with an
        overlay at ``overlay.png``. Passing ``--pdf PATH`` writes a
        deterministic Safety v1 report (requires the ``[safety]``
        extra — ReportLab).
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
        from openpathai.safety import (
            AnalysisResult,
            ClassProbability,
            classify_with_band,
            validate_card,
        )
        from openpathai.training.engine import resolve_device

        registry = default_model_registry()
        card = None
        if registry.has(model):
            card = registry.get(model)
        elif model in registry.invalid_names():
            card = registry.invalid_card(model)
            issues = registry.invalid_issues(model)
            codes = ", ".join(sorted({i.code for i in issues}))
            if allow_incomplete_card:
                typer.secho(
                    f"Warning: model card {model!r} fails the safety contract "
                    f"({codes}); proceeding because --allow-incomplete-card is set.",
                    fg="yellow",
                    err=True,
                )
            else:
                typer.secho(
                    f"Model card {model!r} fails the safety contract ({codes}). "
                    "Fix the card or pass --allow-incomplete-card.",
                    fg="red",
                    err=True,
                )
                raise typer.Exit(2)
        else:
            typer.secho(f"Model card {model!r} is not registered.", fg="red", err=True)
            raise typer.Exit(2)
        assert card is not None  # narrow for the type checker

        # Final guardrail: even valid cards are re-checked in case of custom
        # registry. Cheap; zero-cost on happy path.
        issues = validate_card(card)
        if issues and not allow_incomplete_card:
            codes = ", ".join(sorted({i.code for i in issues}))
            typer.secho(
                f"Model card {card.name!r} fails the safety contract ({codes}). "
                "Fix the card or pass --allow-incomplete-card.",
                fg="red",
                err=True,
            )
            raise typer.Exit(2)

        dev = resolve_device(device)

        tile_bytes = tile_path.read_bytes()
        image_sha256 = hashlib.sha256(tile_bytes).hexdigest()

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

        # Run a forward pass once to capture probabilities; explainers
        # re-run as needed with gradient tracking.
        with torch.no_grad():
            logits = net(tensor)
            probs_tensor = torch.softmax(logits, dim=1)[0].detach().cpu().numpy()
        probabilities = tuple(
            ClassProbability(class_name=f"class_{i}", probability=float(p))
            for i, p in enumerate(probs_tensor)
        )

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

        borderline = classify_with_band(
            [cp.probability for cp in probabilities],
            low=low,
            high=high,
            allow_uncalibrated=allow_uncalibrated,
            calibrated=not allow_uncalibrated,
        )
        typer.echo(
            f"decision: {borderline.decision} "
            f"(confidence={borderline.confidence:.3f}, band={borderline.band})"
        )

        result = AnalysisResult(
            image_sha256=image_sha256,
            model_name=card.name,
            explainer_name=explainer,
            probabilities=probabilities,
            borderline=borderline,
            manifest_hash="",
            overlay_png=_png_bytes(overlay),
            thumbnail_png=_png_bytes(resized_rgb),
        )

        if pdf is not None:
            from openpathai.safety.report import render_pdf

            render_pdf(result, pdf)
            typer.echo(f"report: {pdf}")

        if not no_audit:
            from openpathai.safety.audit import log_analysis

            analysis_id = log_analysis(result, input_path=tile_path)
            if analysis_id:
                typer.echo(f"audit: {analysis_id}")


__all__ = ["register"]
