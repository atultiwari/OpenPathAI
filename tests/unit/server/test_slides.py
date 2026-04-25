"""Phase 21 — slide upload + DZI tile serving."""

from __future__ import annotations

import io
from xml.etree import ElementTree as ET

import numpy as np
import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from PIL import Image


def _png_bytes(size: tuple[int, int] = (512, 384)) -> bytes:
    arr = np.random.default_rng(7).integers(0, 255, size=(size[1], size[0], 3), dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def test_upload_then_get_dzi_descriptor(client: TestClient, auth_headers: dict[str, str]) -> None:
    payload = _png_bytes()
    response = client.post(
        "/v1/slides",
        headers=auth_headers,
        files={"file": ("synthetic.png", payload, "image/png")},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    sid = body["slide_id"]
    assert len(sid) == 64
    assert body["filename"] == "synthetic.png"
    assert body["dzi_url"] == f"/v1/slides/{sid}.dzi"
    assert body["width"] == 512
    assert body["height"] == 384
    assert body["backend"] in {"pillow", "openslide"}

    # Fetching the descriptor returns valid DZI XML.
    descriptor = client.get(body["dzi_url"], headers=auth_headers)
    assert descriptor.status_code == 200
    assert descriptor.headers["content-type"].startswith("application/xml")
    root = ET.fromstring(descriptor.content)
    assert root.tag.endswith("Image")
    size = root.find("{http://schemas.microsoft.com/deepzoom/2008}Size")
    assert size is not None
    assert size.attrib["Width"] == "512"
    assert size.attrib["Height"] == "384"


def test_dzi_tile_returns_png(client: TestClient, auth_headers: dict[str, str]) -> None:
    upload = client.post(
        "/v1/slides",
        headers=auth_headers,
        files={"file": ("synthetic.png", _png_bytes((128, 96)), "image/png")},
    )
    sid = upload.json()["slide_id"]
    # The deepest level for a 128x96 image is ceil(log2(128)) = 7.
    response = client.get(f"/v1/slides/{sid}_files/7/0_0.png", headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    decoded = Image.open(io.BytesIO(response.content))
    assert decoded.format == "PNG"


def test_list_slides_paginates(client: TestClient, auth_headers: dict[str, str]) -> None:
    for n in range(3):
        client.post(
            "/v1/slides",
            headers=auth_headers,
            files={"file": (f"s{n}.png", _png_bytes((64 + n, 48 + n)), "image/png")},
        )
    response = client.get("/v1/slides", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 3
    assert all(item["dzi_url"].endswith(".dzi") for item in body["items"])


def test_delete_slide_removes_metadata(client: TestClient, auth_headers: dict[str, str]) -> None:
    upload = client.post(
        "/v1/slides",
        headers=auth_headers,
        files={"file": ("g.png", _png_bytes((48, 48)), "image/png")},
    )
    sid = upload.json()["slide_id"]
    delete = client.delete(f"/v1/slides/{sid}", headers=auth_headers)
    assert delete.status_code == 204
    follow = client.get(f"/v1/slides/{sid}", headers=auth_headers)
    assert follow.status_code == 404


def test_invalid_slide_id_rejected(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/v1/slides/not_hex.dzi", headers=auth_headers)
    assert response.status_code in {400, 404}


def test_empty_upload_rejected(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/v1/slides",
        headers=auth_headers,
        files={"file": ("empty.png", b"", "image/png")},
    )
    assert response.status_code == 422


def test_oversized_slide_is_downsampled_for_dzi(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A slide larger than ``MAX_DZI_BASE_LONGEST_AXIS`` (8192 px) must
    upload cleanly and the DZI descriptor must reflect the downsampled
    base — not the native dimensions — so OpenSeadragon doesn't ask
    for tiles that don't exist.

    Pillow's decompression-bomb cap is also disabled at the WSI reader,
    so this test doubles as a regression for the HISTAI-breast slide
    upload (~4 Gpx, native).
    """
    # 9000 x 6000 synthetic TIFF — bigger than the 8192 cap so the
    # downsampling branch fires, small enough that the test is fast.
    arr = np.full((6000, 9000, 3), 200, dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="TIFF")
    response = client.post(
        "/v1/slides",
        headers=auth_headers,
        files={"file": ("oversize.tif", buf.getvalue(), "image/tiff")},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    sid = body["slide_id"]
    # Native dimensions are reported as-is.
    assert body["width"] == 9000
    assert body["height"] == 6000
    # DZI descriptor reflects the clamped base.
    descriptor = client.get(body["dzi_url"], headers=auth_headers)
    assert descriptor.status_code == 200
    root = ET.fromstring(descriptor.content)
    size = root.find("{http://schemas.microsoft.com/deepzoom/2008}Size")
    assert size is not None
    assert int(size.attrib["Width"]) <= 8192
    assert int(size.attrib["Width"]) >= 8000
    # Top-of-pyramid tile is renderable.
    tile = client.get(f"/v1/slides/{sid}_files/0/0_0.png", headers=auth_headers)
    assert tile.status_code == 200
