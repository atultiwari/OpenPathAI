"""register_folder / deregister_folder / list_local — library surface."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PIL import Image

from openpathai.data import (
    deregister_folder,
    list_local,
    register_folder,
)
from openpathai.data.cards import DatasetCard
from openpathai.data.local import user_datasets_dir


@pytest.fixture
def imagefolder(tmp_path: Path) -> Path:
    """Build a tiny ImageFolder-style tree for tests to register."""
    root = tmp_path / "tree"
    for cls in ("normal", "tumour"):
        (root / cls).mkdir(parents=True)
        for i in range(3):
            arr_bytes = bytes([i * 8 + 5] * (16 * 16 * 3))
            Image.frombytes("RGB", (16, 16), arr_bytes).save(
                root / cls / f"{cls}_{i}.png",
                format="PNG",
            )
    return root


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect OPENPATHAI_HOME so user-registered cards never leak out."""
    monkeypatch.setenv("OPENPATHAI_HOME", str(tmp_path / "openpathai_home"))


def test_register_infers_classes(imagefolder: Path) -> None:
    card = register_folder(imagefolder, name="mini", tissue=("colon",))
    assert isinstance(card, DatasetCard)
    assert card.classes == ("normal", "tumour")
    assert card.num_classes == 2
    assert card.total_images == 6
    assert card.download.method == "local"
    assert card.download.local_path is not None
    assert card.download.local_path.resolve() == imagefolder.resolve()
    assert "fingerprint=" in (card.download.partial_download_hint or "")


def test_yaml_written_to_user_dir(imagefolder: Path) -> None:
    register_folder(imagefolder, name="mini", tissue=("colon",))
    yaml_path = user_datasets_dir() / "mini.yaml"
    assert yaml_path.is_file()


def test_fingerprint_stable_across_runs(imagefolder: Path) -> None:
    a = register_folder(imagefolder, name="a", tissue=("colon",))
    b = register_folder(imagefolder, name="b", tissue=("colon",))
    assert a.download.partial_download_hint == b.download.partial_download_hint


def test_overwrite_guard(imagefolder: Path) -> None:
    register_folder(imagefolder, name="mini", tissue=("colon",))
    with pytest.raises(FileExistsError):
        register_folder(imagefolder, name="mini", tissue=("colon",))
    register_folder(imagefolder, name="mini", tissue=("colon",), overwrite=True)


def test_rejects_empty_tree(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError, match="No class"):
        register_folder(empty, name="mini", tissue=("colon",))


def test_rejects_non_directory(tmp_path: Path) -> None:
    not_a_dir = tmp_path / "notadir.txt"
    not_a_dir.write_text("x")
    with pytest.raises(NotADirectoryError):
        register_folder(not_a_dir, name="mini", tissue=("colon",))


def test_declared_classes_must_exist(imagefolder: Path) -> None:
    with pytest.raises(ValueError, match="Declared classes"):
        register_folder(
            imagefolder,
            name="mini",
            tissue=("colon",),
            classes=("normal", "missing"),
        )


def test_wsi_modality_rejected(imagefolder: Path) -> None:
    with pytest.raises(ValueError, match=r"Phase 9|tile modality"):
        register_folder(imagefolder, name="mini", tissue=("colon",), modality="wsi")


def test_list_local_and_deregister(imagefolder: Path) -> None:
    assert list_local() == ()
    register_folder(imagefolder, name="mini", tissue=("colon",))
    cards = list_local()
    assert {c.name for c in cards} == {"mini"}
    assert deregister_folder("mini") is True
    assert list_local() == ()
    assert deregister_folder("mini") is False


def test_register_performance(imagefolder: Path) -> None:
    """Registering a small tree should be <250 ms (fingerprint is path+size)."""
    import time

    start = time.perf_counter()
    register_folder(imagefolder, name="mini", tissue=("colon",))
    elapsed = time.perf_counter() - start
    assert elapsed < 0.25, f"register_folder took {elapsed:.3f}s, expected <0.25s"


def test_registry_discovers_user_card(imagefolder: Path) -> None:
    from openpathai.data.registry import DatasetRegistry

    register_folder(imagefolder, name="discover_me", tissue=("colon",))
    reg = DatasetRegistry(include_repo=False)
    assert "discover_me" in reg.names()
    card = reg.get("discover_me")
    assert card.download.method == "local"


def test_openpathai_home_override_is_respected(imagefolder: Path, tmp_path: Path) -> None:
    target = tmp_path / "alt_home"
    os.environ["OPENPATHAI_HOME"] = str(target)
    register_folder(imagefolder, name="override", tissue=("colon",))
    assert (target / "datasets" / "override.yaml").is_file()
