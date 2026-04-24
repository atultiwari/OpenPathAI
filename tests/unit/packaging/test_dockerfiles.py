"""Phase 18 — Dockerfile structural checks.

We don't actually `docker build` in unit tests (too slow +
needs the docker daemon). Instead we grep the Dockerfiles for
invariants that are easy to drift on:

* non-root user + predictable uid;
* ENTRYPOINT points at the CLI;
* every `RUN pipx install` names at least one extra;
* the GPU image pins a CUDA version.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def cpu_dockerfile() -> str:
    return (ROOT / "docker" / "Dockerfile.cpu").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def gpu_dockerfile() -> str:
    return (ROOT / "docker" / "Dockerfile.gpu").read_text(encoding="utf-8")


def test_cpu_image_has_entrypoint_openpathai(cpu_dockerfile: str) -> None:
    assert 'ENTRYPOINT ["openpathai"]' in cpu_dockerfile


def test_gpu_image_has_entrypoint_openpathai(gpu_dockerfile: str) -> None:
    assert 'ENTRYPOINT ["openpathai"]' in gpu_dockerfile


def test_cpu_image_runs_as_non_root(cpu_dockerfile: str) -> None:
    assert "useradd --create-home --uid 1000 openpathai" in cpu_dockerfile
    assert "USER openpathai" in cpu_dockerfile


def test_gpu_image_runs_as_non_root(gpu_dockerfile: str) -> None:
    assert "useradd --create-home --uid 1000 openpathai" in gpu_dockerfile
    assert "USER openpathai" in gpu_dockerfile


def test_pipx_install_always_specifies_extras(cpu_dockerfile: str) -> None:
    # Each `pipx install` line must include a `[…]` extras spec.
    for line in cpu_dockerfile.splitlines():
        if "pipx install" in line and "--force" in line:
            assert "[" in line, f"pipx install missing extras: {line!r}"


def test_gpu_image_pins_cuda(gpu_dockerfile: str) -> None:
    assert "nvidia/cuda:" in gpu_dockerfile
    # A version tag (not a rolling latest).
    assert "nvidia/cuda:latest" not in gpu_dockerfile


def test_cpu_image_uses_slim_python(cpu_dockerfile: str) -> None:
    assert "python:3.12-slim-bookworm" in cpu_dockerfile


def test_workflow_exists_and_gates_on_secret() -> None:
    workflow = (ROOT / ".github" / "workflows" / "docker.yml").read_text(encoding="utf-8")
    # Workflow must fire on push to main, not every branch.
    assert "branches: [main]" in workflow
    # Both jobs gate push + login on the GHCR_TOKEN secret so forks build
    # cleanly. The secret is evaluated via a prior shell step that writes
    # a `can_push` output consumed by downstream `if:` expressions — the
    # older direct ``secrets.GHCR_TOKEN != ''`` in step-level ``if:`` is
    # rejected by GitHub's workflow validator.
    assert "GHCR_TOKEN: ${{ secrets.GHCR_TOKEN }}" in workflow
    assert "steps.ghcr.outputs.can_push == 'true'" in workflow
    # Both tags (cpu + gpu) are produced.
    assert "openpathai:cpu-latest" in workflow
    assert "openpathai:gpu-latest" in workflow


def test_docker_readme_covers_both_images() -> None:
    readme = (ROOT / "docker" / "README.md").read_text(encoding="utf-8")
    assert "Dockerfile.cpu" in readme
    assert "Dockerfile.gpu" in readme
    assert "--gpus all" in readme
