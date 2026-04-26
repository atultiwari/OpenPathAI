"""Phase 22.0 chunk A — dataset structure analyser."""

from __future__ import annotations

from pathlib import Path

import pytest

from openpathai.data.analyse import analyse_folder


def _seed_imagefolder(root: Path, classes: dict[str, int]) -> None:
    for name, n in classes.items():
        cdir = root / name
        cdir.mkdir(parents=True)
        for i in range(n):
            (cdir / f"tile_{i}.png").write_bytes(b"x" * 64)


def test_missing_path() -> None:
    report = analyse_folder("/no/such/path/here")
    assert report.exists is False
    assert report.layout == "missing"
    assert report.image_count == 0


def test_path_is_a_file(tmp_path: Path) -> None:
    p = tmp_path / "a.png"
    p.write_bytes(b"x")
    report = analyse_folder(p)
    assert report.exists is True
    assert report.is_directory is False
    assert report.layout == "not_a_directory"


def test_imagefolder_layout(tmp_path: Path) -> None:
    _seed_imagefolder(tmp_path, {"class_a": 4, "class_b": 6, "class_c": 5})
    report = analyse_folder(tmp_path)
    assert report.layout == "image_folder"
    assert report.class_count == 3
    assert report.image_count == 15
    by_name = {c.name: c.count for c in report.classes}
    assert by_name == {"class_a": 4, "class_b": 6, "class_c": 5}
    assert report.suggested_root is None
    assert ".png" in report.extensions
    assert report.bytes_total > 0


def test_nested_imagefolder_kather_case(tmp_path: Path) -> None:
    """Phase 22.0 — exact reproduction of the user's Kather folder shape:
    parent contains an inner ImageFolder + a sibling folder of larger
    images + some flat CSV dumps + .DS_Store. Analyser must point at the
    inner folder via suggested_root."""
    parent = tmp_path / "Kather_Colorectal_Carcinoma"
    parent.mkdir()
    inner = parent / "Kather_texture_2016_image_tiles_5000"
    _seed_imagefolder(
        inner,
        {f"class_{i:02d}": 5 for i in range(8)},
    )
    # Sibling non-class folder.
    siblings = parent / "Kather_texture_2016_larger_images_10"
    siblings.mkdir()
    (siblings / "huge.tif").write_bytes(b"x" * 128)
    # Flat CSV dumps and a .DS_Store.
    (parent / ".DS_Store").write_bytes(b"\x00")
    for n in ("hmnist_28_28_RGB.csv", "hmnist_64_64_L.csv"):
        (parent / n).write_bytes(b"a,b,c\n")

    report = analyse_folder(parent)
    assert report.layout == "nested_image_folder"
    assert report.suggested_root is not None
    assert report.suggested_root.endswith("Kather_texture_2016_image_tiles_5000")
    # The .DS_Store and CSV dumps are surfaced as warnings, not errors.
    assert any(".DS_Store" in w for w in report.hidden_entries)
    assert any("non-image file" in w.lower() for w in report.warnings)


def test_flat_layout_is_not_imagefolder(tmp_path: Path) -> None:
    for i in range(3):
        (tmp_path / f"tile_{i}.png").write_bytes(b"x")
    report = analyse_folder(tmp_path)
    assert report.layout == "flat"
    assert report.class_count == 0
    assert report.image_count == 3
    assert any("loose images at the root" in w.lower() for w in report.warnings)


def test_csv_only_layout(tmp_path: Path) -> None:
    (tmp_path / "hmnist_28_28_RGB.csv").write_bytes(b"a,b\n")
    report = analyse_folder(tmp_path)
    assert report.layout == "csv_only"
    assert report.image_count == 0
    assert any("MNIST-style" in w for w in report.warnings)


def test_single_class_warning(tmp_path: Path) -> None:
    _seed_imagefolder(tmp_path, {"only_class": 4})
    report = analyse_folder(tmp_path)
    assert report.layout == "image_folder"
    assert report.class_count == 1
    assert any("Only one class" in w or "≥ 2 classes" in w for w in report.warnings)


def test_class_imbalance_warning(tmp_path: Path) -> None:
    _seed_imagefolder(tmp_path, {"big": 100, "tiny": 5})
    report = analyse_folder(tmp_path)
    assert report.layout == "image_folder"
    assert any("imbalance" in w.lower() for w in report.warnings)


def test_empty_folder(tmp_path: Path) -> None:
    report = analyse_folder(tmp_path)
    assert report.layout == "empty"
    assert report.image_count == 0


def test_route_round_trip_against_kather_shape(tmp_path: Path) -> None:
    """End-to-end via the FastAPI route. The wizard will call this
    with exactly the user-supplied path; the response shape is the
    contract."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from openpathai.server.app import create_app
    from openpathai.server.config import ServerSettings

    parent = tmp_path / "Kather_Colorectal_Carcinoma"
    inner = parent / "Kather_texture_2016_image_tiles_5000"
    _seed_imagefolder(inner, {f"class_{i}": 4 for i in range(8)})

    settings = ServerSettings(
        token="test-token-1234567890abcdef",
        openpathai_home=tmp_path / "opa-home",
        pipelines_dir=tmp_path / "opa-home" / "pipelines",
    )
    app = create_app(settings)
    with TestClient(app) as client:
        response = client.post(
            "/v1/datasets/analyse",
            headers={"Authorization": f"Bearer {settings.token}"},
            json={"path": str(parent)},
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["layout"] == "nested_image_folder"
    assert body["suggested_root"].endswith("Kather_texture_2016_image_tiles_5000")
