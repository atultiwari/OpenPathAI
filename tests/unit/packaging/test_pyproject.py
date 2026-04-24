"""Phase 18 — pyproject.toml structural contract."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def pyproject() -> dict:
    with (ROOT / "pyproject.toml").open("rb") as fh:
        return tomllib.load(fh)


def test_project_basics(pyproject: dict) -> None:
    project = pyproject["project"]
    assert project["name"] == "openpathai"
    assert project["requires-python"].startswith(">=3.11")
    assert project["readme"] == "README.md"
    assert project["license"] == "MIT"


def test_cli_entry_point_registered(pyproject: dict) -> None:
    scripts = pyproject["project"]["scripts"]
    assert scripts["openpathai"] == "openpathai.cli.main:app"


def test_core_deps_include_http_and_crypto(pyproject: dict) -> None:
    """Phase 15 + 17 elevated httpx + cryptography to core deps;
    the CLI chain crashes without them."""
    deps_raw = pyproject["project"]["dependencies"]
    dep_names = {line.split(">=")[0].split("<")[0].split("[")[0].strip() for line in deps_raw}
    for required in ("numpy", "pydantic", "pyyaml", "typer", "httpx", "cryptography"):
        assert required in dep_names, f"core dep {required!r} missing"


def test_classifiers_include_beta_and_py313(pyproject: dict) -> None:
    classifiers = pyproject["project"]["classifiers"]
    # Phase 18 bumps to Beta.
    assert any("Development Status :: 4 - Beta" in c for c in classifiers)
    # Python 3.13 support landed via the torch>=2.6 pin.
    assert any("Python :: 3.13" in c for c in classifiers)
    # MIT licence declared both as an SPDX + classifier for PyPI discoverability.
    assert any("License :: OSI Approved :: MIT" in c for c in classifiers)


def test_expected_extras_ship(pyproject: dict) -> None:
    extras = pyproject["project"].get("optional-dependencies", {})
    # Every extra that cli/main.py transitively references must be present
    # so `pipx install "openpathai[<x>]"` works on a fresh machine.
    for name in ("dev", "gui", "train", "safety", "audit", "explain", "mlflow", "notebook"):
        assert name in extras, f"extra {name!r} missing from pyproject"


def test_readme_exists_and_is_product_shaped() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    # Phase 18 README rewrite replaced the pre-alpha banner.
    assert "pre-alpha · Phase 0" not in readme
    assert "Install" in readme
    assert "What's in the box" in readme


def test_build_system_is_hatchling(pyproject: dict) -> None:
    build = pyproject["build-system"]
    assert build["build-backend"].startswith("hatchling")
