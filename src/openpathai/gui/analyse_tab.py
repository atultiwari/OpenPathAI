"""Analyse tab — upload tile, pick model + explainer, generate heatmap."""

from __future__ import annotations

from typing import Any

from openpathai.gui.state import AppState
from openpathai.gui.views import (
    device_choices,
    explainer_choices,
    target_layer_hint,
)
from openpathai.models import default_model_registry


def _resolve_target_layer(model_name: str, fallback: str) -> str:  # pragma: no cover - gradio
    if fallback:
        return fallback
    return target_layer_hint(model_name) or ""


def _run_analysis(  # pragma: no cover - torch-gated
    image,
    model_name: str,
    explainer: str,
    target_layer: str,
    target_class: int,
    device: str,
):
    """Bridge from Gradio widgets to the Phase 4 explainers."""
    import importlib.util

    if importlib.util.find_spec("torch") is None:
        return None, None, "Install the `[train]` extra (torch + timm) to generate heatmaps."
    import numpy as np
    import torch
    from PIL import Image

    from openpathai.explain.base import overlay_on_tile
    from openpathai.explain.gradcam import EigenCAM, GradCAM, GradCAMPlusPlus
    from openpathai.explain.integrated_gradients import integrated_gradients
    from openpathai.models import adapter_for_card
    from openpathai.training.engine import resolve_device

    if image is None:
        return None, None, "Upload a tile image first."

    registry = default_model_registry()
    if not registry.has(model_name):
        return None, None, f"Model card {model_name!r} is not registered."
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

    if explainer == "gradcam":
        heatmap = GradCAM(net, layer).explain(tensor, target_class, output_size=(height, width))
    elif explainer == "gradcam_plus_plus":
        heatmap = GradCAMPlusPlus(net, layer).explain(
            tensor, target_class, output_size=(height, width)
        )
    elif explainer == "eigencam":
        heatmap = EigenCAM(net, layer).explain(tensor, output_size=(height, width))
    elif explainer == "integrated_gradients":
        heatmap = integrated_gradients(net, tensor, target_class, output_size=(height, width))
    else:
        return None, None, f"Explainer {explainer!r} is not supported in the Analyse tab yet."

    heatmap_u8 = (np.clip(heatmap, 0.0, 1.0) * 255).astype(np.uint8)
    overlay = overlay_on_tile(resized, heatmap)
    return heatmap_u8, overlay, f"Generated heatmap via {explainer}."


def build(state: AppState) -> Any:  # pragma: no cover - gradio-gated renderer
    import gradio as gr

    with gr.Blocks() as tab:
        gr.Markdown(
            "### Analyse a tile\n"
            "Pick a model, pick an explainer, click **Generate**. "
            "Requires the `[train]` extra (torch + timm)."
        )
        with gr.Row():
            image = gr.Image(label="Tile", type="numpy")
            with gr.Column():
                model = gr.Dropdown(
                    default_model_registry().names(),
                    value=state.selected_model or "resnet18",
                    label="Model card",
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
                generate = gr.Button("Generate")
        status = gr.Markdown("")
        with gr.Row():
            heatmap = gr.Image(label="Heatmap", type="numpy")
            overlay = gr.Image(label="Overlay", type="numpy")
        generate.click(
            _run_analysis,
            inputs=[image, model, explainer, target_layer, target_class, device],
            outputs=[heatmap, overlay, status],
        )
    return tab


__all__ = ["build"]
