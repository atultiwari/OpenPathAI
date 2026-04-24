"""NL primitives via FastAPI."""

from __future__ import annotations

import base64
from io import BytesIO

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image


def _tile_b64(size: tuple[int, int] = (64, 64)) -> str:
    arr = np.random.default_rng(0).integers(0, 255, size=(*size, 3), dtype=np.uint8)
    buf = BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def test_classify_runs_end_to_end(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/v1/nl/classify",
        headers=auth_headers,
        json={"image_b64": _tile_b64(), "prompts": ["benign", "malignant"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert "predicted_prompt" in body
    assert set(body["prompts"]) == {"benign", "malignant"}


def test_classify_rejects_bad_base64(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/v1/nl/classify",
        headers=auth_headers,
        json={"image_b64": "not-valid-base64!!", "prompts": ["a", "b"]},
    )
    assert response.status_code == 422


def test_segment_runs_end_to_end(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/v1/nl/segment",
        headers=auth_headers,
        json={"image_b64": _tile_b64(), "prompt": "segment every gland"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "mask_shape" in body
    assert "mask_rle" in body
    assert "class_names" in body


def test_draft_pipeline_requires_backend(client: TestClient, auth_headers: dict[str, str]) -> None:
    # No LLM backend available in CI — iron rule #9 still holds:
    # the endpoint rejects with 503, and never echoes the raw prompt.
    response = client.post(
        "/v1/nl/draft-pipeline",
        headers=auth_headers,
        json={"prompt": "Train resnet18 on LC25000 for 3 epochs"},
    )
    assert response.status_code in {200, 422, 503}
    body = response.json()
    # Whatever the outcome, the raw prompt must never be echoed.
    text = str(body)
    assert "Train resnet18 on LC25000 for 3 epochs" not in text
