"""Analyse tab — upload tile, pick model + explainer, generate heatmap.

Phase 7 extensions:

* **Borderline band** inputs (low / high) and a coloured badge on the
  output.
* **Per-class probabilities** DataFrame.
* **Model card** accordion surfacing the safety-contract fields.
* **Download PDF report** button that routes through
  :func:`openpathai.safety.report.render_pdf`.
"""

from __future__ import annotations

import hashlib
import io
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openpathai.gui.state import AppState
from openpathai.gui.views import (
    borderline_badge,
    device_choices,
    explainer_choices,
    model_card_snippet,
    probability_rows,
    target_layer_hint,
)
from openpathai.models import default_model_registry


@dataclass
class _AnalyseRunState:
    """Cached outputs of the most recent Generate click.

    Re-used by the Download PDF button so the user does not re-infer.
    """

    ready: bool = False
    image_sha256: str = ""
    model_name: str = ""
    explainer_name: str = ""
    probabilities_names: list[str] = field(default_factory=list)
    probabilities_values: list[float] = field(default_factory=list)
    borderline: Any = None
    overlay_png: bytes = b""
    thumbnail_png: bytes = b""


def _resolve_target_layer(model_name: str, fallback: str) -> str:  # pragma: no cover - gradio
    if fallback:
        return fallback
    return target_layer_hint(model_name) or ""


def _png_bytes(arr: Any) -> bytes:  # pragma: no cover - gradio
    """Encode an ndarray as PNG bytes (deterministic)."""
    from PIL import Image

    buf = io.BytesIO()
    mode = "RGB" if arr.ndim == 3 and arr.shape[-1] == 3 else "L"
    Image.fromarray(arr, mode=mode).save(buf, format="PNG", optimize=False)
    return buf.getvalue()


def _run_analysis(  # pragma: no cover - torch-gated
    image,
    model_name: str,
    explainer: str,
    target_layer: str,
    target_class: int,
    device: str,
    low: float,
    high: float,
    allow_uncalibrated: bool,
    run_state: _AnalyseRunState,
):
    """Bridge from Gradio widgets to the Phase 4 explainers + Phase 7 safety."""
    import importlib.util

    if importlib.util.find_spec("torch") is None:
        return (
            None,
            None,
            "Install the `[train]` extra (torch + timm) to generate heatmaps.",
            borderline_badge("review", "between"),
            [],
            {},
            run_state,
        )
    import numpy as np
    import torch
    from PIL import Image

    from openpathai.explain.base import overlay_on_tile
    from openpathai.explain.gradcam import EigenCAM, GradCAM, GradCAMPlusPlus
    from openpathai.explain.integrated_gradients import integrated_gradients
    from openpathai.models import adapter_for_card
    from openpathai.safety import classify_with_band
    from openpathai.training.engine import resolve_device

    if image is None:
        return (
            None,
            None,
            "Upload a tile image first.",
            borderline_badge("review", "between"),
            [],
            {},
            run_state,
        )

    registry = default_model_registry()
    if not registry.has(model_name):
        msg = f"Model card {model_name!r} is not registered (or failed the safety contract)."
        return (None, None, msg, borderline_badge("review", "between"), [], {}, run_state)
    card = registry.get(model_name)
    dev = resolve_device(device)
    layer = _resolve_target_layer(model_name, target_layer)

    if isinstance(image, np.ndarray):
        rgb = image.astype(np.uint8)
    else:
        rgb = np.asarray(Image.fromarray(np.asarray(image)).convert("RGB"), dtype=np.uint8)
    height, width = card.input_size
    resized = np.asarray(
        Image.fromarray(rgb).resize((width, height), Image.Resampling.BILINEAR),
        dtype=np.uint8,
    )
    tensor = (
        torch.from_numpy(resized.astype(np.float32) / 255.0).permute(2, 0, 1).unsqueeze(0).to(dev)
    )
    mean = torch.tensor(card.preprocessing_mean, device=dev).view(1, 3, 1, 1)
    std = torch.tensor(card.preprocessing_std, device=dev).view(1, 3, 1, 1)
    tensor = (tensor - mean) / std

    adapter = adapter_for_card(card)
    net = adapter.build(card, num_classes=2, pretrained=False).to(dev)
    net.eval()

    with torch.no_grad():
        logits = net(tensor)
        probs = torch.softmax(logits, dim=1)[0].detach().cpu().numpy()

    if explainer == "gradcam":
        heatmap = GradCAM(net, layer).explain(
            tensor, int(target_class), output_size=(height, width)
        )
    elif explainer == "gradcam_plus_plus":
        heatmap = GradCAMPlusPlus(net, layer).explain(
            tensor, int(target_class), output_size=(height, width)
        )
    elif explainer == "eigencam":
        heatmap = EigenCAM(net, layer).explain(tensor, output_size=(height, width))
    elif explainer == "integrated_gradients":
        heatmap = integrated_gradients(net, tensor, int(target_class), output_size=(height, width))
    else:
        return (
            None,
            None,
            f"Explainer {explainer!r} is not supported in the Analyse tab yet.",
            borderline_badge("review", "between"),
            [],
            {},
            run_state,
        )

    heatmap_u8 = (np.clip(heatmap, 0.0, 1.0) * 255).astype(np.uint8)
    overlay = overlay_on_tile(resized, heatmap)

    try:
        decision = classify_with_band(
            list(probs),
            low=float(low),
            high=float(high),
            allow_uncalibrated=bool(allow_uncalibrated),
            calibrated=not bool(allow_uncalibrated),
        )
    except ValueError as exc:
        return (
            heatmap_u8,
            overlay,
            f"Borderline: {exc}",
            borderline_badge("review", "between"),
            [],
            {},
            run_state,
        )

    class_names = [f"class_{i}" for i in range(len(probs))]
    badge = borderline_badge(decision.decision, decision.band)
    prob_table = probability_rows(class_names, list(probs))
    snippet = model_card_snippet(card.name)
    status = (
        f"Generated heatmap via {explainer}. "
        f"Decision={decision.decision} confidence={decision.confidence:.3f} "
        f"band=[{decision.low:.2f}, {decision.high:.2f}]."
    )

    run_state.ready = True
    run_state.image_sha256 = hashlib.sha256(_png_bytes(resized)).hexdigest()
    run_state.model_name = card.name
    run_state.explainer_name = explainer
    run_state.probabilities_names = class_names
    run_state.probabilities_values = [float(p) for p in probs]
    run_state.borderline = decision
    run_state.overlay_png = _png_bytes(overlay)
    run_state.thumbnail_png = _png_bytes(resized)

    # Phase 8 audit log — fire-and-forget; never raises.
    from openpathai.safety import AnalysisResult, ClassProbability
    from openpathai.safety.audit import log_analysis

    log_result = AnalysisResult(
        image_sha256=run_state.image_sha256,
        model_name=run_state.model_name,
        explainer_name=run_state.explainer_name,
        probabilities=tuple(
            ClassProbability(class_name=n, probability=p)
            for n, p in zip(class_names, run_state.probabilities_values, strict=False)
        ),
        borderline=decision,
        manifest_hash="",
        overlay_png=run_state.overlay_png,
        thumbnail_png=run_state.thumbnail_png,
    )
    log_analysis(log_result)

    return heatmap_u8, overlay, status, badge, prob_table, snippet, run_state


def _download_pdf(run_state: _AnalyseRunState, caption: str):  # pragma: no cover - gradio
    """Render the PDF and return a path Gradio can serve as a download."""
    from openpathai.safety import AnalysisResult, ClassProbability
    from openpathai.safety.report import ReportRenderError, render_pdf

    if not run_state.ready:
        return None, "Run Generate first — there is nothing to export."
    probabilities = tuple(
        ClassProbability(class_name=n, probability=p)
        for n, p in zip(
            run_state.probabilities_names,
            run_state.probabilities_values,
            strict=False,
        )
    )
    result = AnalysisResult(
        image_sha256=run_state.image_sha256,
        model_name=run_state.model_name,
        explainer_name=run_state.explainer_name,
        probabilities=probabilities,
        borderline=run_state.borderline,
        manifest_hash="",
        overlay_png=run_state.overlay_png,
        thumbnail_png=run_state.thumbnail_png,
        image_caption=(caption or "").strip(),
    )
    out_path = Path(tempfile.mkdtemp(prefix="openpathai_pdf_")) / "report.pdf"
    try:
        render_pdf(result, out_path)
    except ReportRenderError as exc:
        return None, f"PDF render failed: {exc}"
    return str(out_path), f"Report written to {out_path}."


def build(state: AppState) -> Any:  # pragma: no cover - gradio-gated renderer
    import gradio as gr

    registry = default_model_registry()
    with gr.Blocks() as tab:
        gr.Markdown(
            "### Analyse a tile\n"
            "Pick a model, pick an explainer, click **Generate**. "
            "Requires the `[train]` extra (torch + timm). Safety v1 "
            "surfaces the borderline band, per-class probabilities, the "
            "model-card snippet, and a deterministic PDF report."
        )
        run_state = gr.State(value=_AnalyseRunState())
        with gr.Row():
            image = gr.Image(label="Tile", type="numpy")
            with gr.Column():
                model = gr.Dropdown(
                    registry.names(),
                    value=state.selected_model or "resnet18",
                    label="Model card (incomplete cards are hidden)",
                )
                explainer = gr.Dropdown(
                    explainer_choices(),
                    value=state.selected_explainer,
                    label="Explainer",
                )
                target_layer = gr.Textbox(
                    label="Target layer (optional — hint shown per family)",
                    value="",
                )
                target_class = gr.Number(value=0, precision=0, label="Target class index")
                device = gr.Dropdown(
                    device_choices(),
                    value=state.device,
                    label="Device",
                )
                with gr.Row():
                    low = gr.Slider(
                        minimum=0.0,
                        maximum=1.0,
                        step=0.01,
                        value=0.4,
                        label="Borderline low",
                    )
                    high = gr.Slider(
                        minimum=0.0,
                        maximum=1.0,
                        step=0.01,
                        value=0.7,
                        label="Borderline high",
                    )
                allow_uncalibrated = gr.Checkbox(
                    label="Allow uncalibrated probabilities (unsafe)",
                    value=False,
                )
                generate = gr.Button("Generate")
        status = gr.Markdown("")
        badge = gr.Markdown("")
        with gr.Row():
            heatmap = gr.Image(label="Heatmap", type="numpy")
            overlay = gr.Image(label="Overlay", type="numpy")
        probs_table = gr.Dataframe(
            headers=["class", "probability"],
            interactive=False,
            label="Per-class probabilities",
        )
        with gr.Accordion("Model card", open=False):
            card_json = gr.JSON(label="Safety-contract fields")
        with gr.Accordion("Download PDF report", open=False):
            caption = gr.Textbox(
                label="Optional caption (avoid filesystem paths)",
                value="",
            )
            pdf_btn = gr.Button("Render PDF")
            pdf_file = gr.File(label="PDF", interactive=False)
            pdf_status = gr.Markdown("")

        generate.click(
            _run_analysis,
            inputs=[
                image,
                model,
                explainer,
                target_layer,
                target_class,
                device,
                low,
                high,
                allow_uncalibrated,
                run_state,
            ],
            outputs=[heatmap, overlay, status, badge, probs_table, card_json, run_state],
        )
        pdf_btn.click(
            _download_pdf,
            inputs=[run_state, caption],
            outputs=[pdf_file, pdf_status],
        )
    return tab


__all__ = ["build"]
