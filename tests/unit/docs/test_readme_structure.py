"""Phase 18 — README structural contract."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _headings(markdown: str) -> list[str]:
    """Return every `## heading` / `### heading` line in order."""
    return [line.strip() for line in markdown.splitlines() if re.match(r"^#{2,3}\s+", line)]


def _text() -> str:
    return (ROOT / "README.md").read_text(encoding="utf-8")


def test_readme_has_install_section() -> None:
    headings = _headings(_text())
    assert any(h.startswith("## Install") for h in headings), (
        f"no Install heading in README; got {headings!r}"
    )


def test_readme_has_thirty_min_tour_section() -> None:
    text = _text()
    assert "30 minutes" in text or "30-min" in text


def test_readme_has_whats_in_the_box() -> None:
    headings = _headings(_text())
    assert any("## What's in the box" in h for h in headings)


def test_readme_has_whats_not_in_the_box() -> None:
    headings = _headings(_text())
    assert any("## What isn't in the box" in h for h in headings)


def test_readme_has_docker_section() -> None:
    headings = _headings(_text())
    assert any(h.startswith("## Docker") for h in headings)


def test_readme_links_to_master_plan() -> None:
    assert "docs/planning/master-plan.md" in _text()


def test_readme_links_to_phase_dashboard() -> None:
    assert "docs/planning/phases/README.md" in _text()


def test_readme_declares_phase_17_state_or_later() -> None:
    # Phase 18 (and later) must not revert the "v1.0 complete"
    # status headline.
    assert "v1.0 feature set complete" in _text() or "v1.0.0 line complete" in _text()


def test_install_doc_exists() -> None:
    assert (ROOT / "docs" / "install.md").exists()


def test_user_guide_doc_exists() -> None:
    assert (ROOT / "docs" / "user-guide.md").exists()


def test_faq_doc_exists() -> None:
    assert (ROOT / "docs" / "faq.md").exists()
