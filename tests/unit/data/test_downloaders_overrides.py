"""Phase 21.6.1 — Zenodo URL builder + dispatch_download overrides."""

from __future__ import annotations

from pathlib import Path

import pytest

from openpathai.data import downloaders


def test_zenodo_record_url_builds_canonical_archive_path() -> None:
    url = downloaders.zenodo_record_url("53169")
    assert url == "https://zenodo.org/record/53169/files/archive.zip?download=1"


def test_zenodo_record_url_strips_zenodo_prefix() -> None:
    url = downloaders.zenodo_record_url("zenodo:53169")
    assert "zenodo.org/record/53169" in url


def test_zenodo_record_url_rejects_blank() -> None:
    with pytest.raises(ValueError):
        downloaders.zenodo_record_url("   ")


def test_local_source_path_takes_priority(tmp_path: Path) -> None:
    """When local_source_path is set, dispatch_download must skip the
    network path entirely and just symlink the directory."""
    from openpathai.data.cards import (
        DatasetCard,
        DatasetCitation,
        DatasetDownload,
    )

    src = tmp_path / "src-data"
    src.mkdir()
    (src / "tile_0.png").write_bytes(b"x" * 16)

    card = DatasetCard(
        name="overrides_test",
        display_name="Overrides Test",
        modality="tile",
        num_classes=2,
        classes=("a", "b"),
        tile_size=(96, 96),
        total_images=1,
        license="CC-BY-4.0",
        tissue=("colon",),
        stain="H&E",
        magnification="20X",
        mpp=0.5,
        download=DatasetDownload(
            method="zenodo",  # would normally raise NotImplementedError
            zenodo_record="999999",
        ),
        citation=DatasetCitation(text="t"),
        notes=None,
    )

    root = tmp_path / "datasets-root"
    result = downloaders.dispatch_download(
        card,
        root=root,
        local_source_path=str(src),
    )
    assert result.method == "local"
    assert result.target_dir == root / "overrides_test"
    assert result.files_written == 1
    # Symlink resolves back to the source.
    assert (root / "overrides_test" / "tile_0.png").read_bytes() == b"x" * 16


def test_override_url_routes_to_url_downloader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Override URL must take priority over the card's declared method."""
    from openpathai.data.cards import (
        DatasetCard,
        DatasetCitation,
        DatasetDownload,
    )

    captured: dict[str, str] = {}

    def fake_from_url(
        name: str, url: str, *, root: Path | None = None, method: str = "http"
    ) -> downloaders.DownloadResult:
        captured["name"] = name
        captured["url"] = url
        captured["method"] = method
        target = (root or tmp_path) / name
        target.mkdir(parents=True, exist_ok=True)
        return downloaders.DownloadResult(
            card_name=name,
            method=method,
            target_dir=target,
            files_written=1,
            bytes_written=42,
        )

    monkeypatch.setattr(downloaders, "download_from_url", fake_from_url)

    card = DatasetCard(
        name="override_url_test",
        display_name="Override URL Test",
        modality="tile",
        num_classes=2,
        classes=("a", "b"),
        tile_size=(96, 96),
        total_images=1,
        license="CC-BY-4.0",
        tissue=("colon",),
        stain="H&E",
        magnification="20X",
        mpp=0.5,
        download=DatasetDownload(
            method="zenodo",
            zenodo_record="999999",
        ),
        citation=DatasetCitation(text="t"),
        notes=None,
    )

    result = downloaders.dispatch_download(
        card,
        root=tmp_path,
        override_url="https://example.com/data.zip",
    )
    assert captured["url"] == "https://example.com/data.zip"
    assert captured["method"] == "http"
    assert result.method == "http"
