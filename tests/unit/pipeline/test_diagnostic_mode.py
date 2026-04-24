"""Iron rule #7 — diagnostic-mode preconditions are enforced at run time."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from pydantic import BaseModel

from openpathai.pipeline.cache import ContentAddressableCache
from openpathai.pipeline.executor import (
    DiagnosticModeError,
    Executor,
    Pipeline,
    PipelineStep,
)
from openpathai.pipeline.node import NodeRegistry, node
from openpathai.pipeline.schema import IntArtifact


class _OneInput(BaseModel):
    value: int


def _init_repo(path: Path) -> None:
    """Make ``path`` a clean git repo with one commit."""
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            "commit",
            "--allow-empty",
            "-m",
            "seed",
            "-q",
        ],
        cwd=path,
        check=True,
    )


def _pipeline(registry: NodeRegistry, mode: str = "diagnostic") -> Pipeline:
    @node(id="diag.identity", registry=registry)
    def identity(cfg: _OneInput) -> IntArtifact:
        return IntArtifact(value=cfg.value)

    return Pipeline(
        id="diag-test",
        mode=mode,  # type: ignore[arg-type]
        steps=[PipelineStep(id="a", op="diag.identity", inputs={"value": 1})],
    )


def _build(tmp_path: Path, *, mode: str = "diagnostic") -> tuple[Executor, Pipeline]:
    registry = NodeRegistry()
    cache = ContentAddressableCache(root=tmp_path / "cache")
    exe = Executor(cache=cache, registry=registry)
    return exe, _pipeline(registry, mode=mode)


def test_diagnostic_mode_requires_clean_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo(tmp_path)
    (tmp_path / "dirty.txt").write_text("x")  # untracked file → dirty
    monkeypatch.delenv("OPENPATHAI_DIAGNOSTIC_SKIP_GIT_CHECK", raising=False)

    exe, pipeline = _build(tmp_path)
    with pytest.raises(DiagnosticModeError, match="not clean"):
        exe.run(pipeline)


def test_diagnostic_mode_requires_git_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Running outside a git checkout must fail diagnostic mode."""
    # HOME and a fresh cwd ensures no ambient git repo is found.
    scratch = tmp_path / "not-a-repo"
    scratch.mkdir()
    monkeypatch.chdir(scratch)
    monkeypatch.delenv("OPENPATHAI_DIAGNOSTIC_SKIP_GIT_CHECK", raising=False)

    exe, pipeline = _build(tmp_path)
    with pytest.raises(DiagnosticModeError):
        exe.run(pipeline)


def test_diagnostic_mode_allows_clean_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo(tmp_path)

    exe, pipeline = _build(tmp_path)
    result = exe.run(pipeline)
    assert result.manifest.mode == "diagnostic"


def test_diagnostic_bypass_env_var_works(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    scratch = tmp_path / "not-a-repo"
    scratch.mkdir()
    monkeypatch.chdir(scratch)
    monkeypatch.setenv("OPENPATHAI_DIAGNOSTIC_SKIP_GIT_CHECK", "1")

    exe, pipeline = _build(tmp_path)
    # Must not raise despite no git tree.
    result = exe.run(pipeline)
    assert result.manifest.mode == "diagnostic"


def test_exploratory_mode_unaffected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Exploratory mode never runs the git check."""
    scratch = tmp_path / "not-a-repo"
    scratch.mkdir()
    monkeypatch.chdir(scratch)
    exe, pipeline = _build(tmp_path, mode="exploratory")
    result = exe.run(pipeline)
    assert result.manifest.mode == "exploratory"
