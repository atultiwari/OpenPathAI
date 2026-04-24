"""DINOv2 adapter — preprocess + end-to-end embed on a random-init module.

We don't download the real DINOv2 weights in CI (needs internet
+ ~90 MB). Instead we exercise the ``preprocess`` path directly
(pure numpy/torch) and use a random-init timm ViT to confirm the
``embed`` plumbing (forward hook, tensor reshaping, numpy cast).
"""

from __future__ import annotations

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from openpathai.foundation.dinov2 import DINOv2SmallAdapter  # noqa: E402


def test_preprocess_numpy_uint8_image() -> None:
    adapter = DINOv2SmallAdapter()
    image = (np.random.default_rng(0).random((224, 224, 3)) * 255).astype(np.uint8)
    tensor = adapter.preprocess(image)
    assert tensor.shape == (1, 3, 224, 224)
    assert tensor.dtype == torch.float32
    # Normalised — mean close to 0, std close to 1 per-channel.
    assert float(tensor.abs().max()) < 5.0


def test_preprocess_accepts_float_tensor() -> None:
    adapter = DINOv2SmallAdapter()
    tensor_in = torch.rand(3, 224, 224)
    tensor = adapter.preprocess(tensor_in)
    assert tensor.shape == (1, 3, 224, 224)


def test_preprocess_accepts_grayscale() -> None:
    adapter = DINOv2SmallAdapter()
    image = (np.random.default_rng(0).random((224, 224)) * 255).astype(np.uint8)
    tensor = adapter.preprocess(image)
    assert tensor.shape == (1, 3, 224, 224)


def test_embed_round_trip_with_random_init_module() -> None:
    """Skip the real weight download; inject a random-init timm
    module directly so we exercise the embed() plumbing without
    requiring an internet fetch in CI. DINOv2-small expects a
    518x518 input (the upstream default), not 224x224."""
    timm = pytest.importorskip("timm")
    adapter = DINOv2SmallAdapter()
    # Random-init == pretrained=False avoids the download path.
    module = timm.create_model(
        "vit_small_patch14_dinov2",
        pretrained=False,
        num_classes=0,
    )
    module.eval()
    adapter._module = module

    # Use the model's own expected input size.
    h, w = module.default_cfg["input_size"][1:]
    image = torch.rand(1, 3, h, w)
    feats = adapter.embed(image)
    assert feats.shape == (1, 384)
    assert feats.dtype == np.float32


def test_attribute_surface_is_frozen_at_class_level() -> None:
    a = DINOv2SmallAdapter()
    assert a.id == "dinov2_vits14"
    assert a.gated is False
    assert a.embedding_dim == 384
    assert a.tier_compatibility == frozenset({"T1", "T2", "T3"})
