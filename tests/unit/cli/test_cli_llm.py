"""``openpathai llm`` CLI — status + pull surface."""

from __future__ import annotations

from typer.testing import CliRunner

from openpathai.cli.main import app
from tests.conftest import strip_ansi

runner = CliRunner(mix_stderr=False)


def test_llm_status_help_exits_0() -> None:
    result = runner.invoke(app, ["llm", "--help"])
    assert result.exit_code == 0
    out = strip_ansi(result.stdout)
    for token in ("status", "pull"):
        assert token in out


def test_llm_status_without_backend_exits_3() -> None:
    """No Ollama / LM Studio running on CI → exit code 3 +
    actionable install message."""
    result = runner.invoke(app, ["llm", "status"])
    assert result.exit_code == 3
    combined = result.stdout + (result.stderr or "")
    # The tabular listing is still printed.
    assert "ollama" in combined
    assert "lmstudio" in combined
    # And the friendly install pointer hits stderr.
    assert "No LLM backend" in combined or "No backend is reachable" in combined


def test_llm_pull_without_ollama_binary_exits_3() -> None:
    """``ollama`` CLI isn't on the CI PATH → exit 3 + pointer."""
    import shutil

    if shutil.which("ollama") is not None:
        # Skip cleanly on dev machines that actually have ollama.
        import pytest

        pytest.skip("ollama CLI installed; this test covers the missing-CLI branch")
    result = runner.invoke(app, ["llm", "pull", "medgemma:1.5"])
    assert result.exit_code == 3
    combined = result.stdout + (result.stderr or "")
    assert "ollama" in combined
