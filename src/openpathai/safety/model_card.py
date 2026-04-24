"""Model-card completeness contract for the safety layer.

Iron rule #10 of ``CLAUDE.md`` says *every model has a card*. Phase 7
turns that from convention into an enforceable contract: the registry
refuses to expose any :class:`~openpathai.models.cards.ModelCard` that
fails :func:`validate_card`.

The contract checks six mandatory fields:

=========================  ======================================================
Field                      Contract
=========================  ======================================================
``training_data``          Non-empty string naming the corpus the weights trained on
``source.license``         Non-empty licence identifier (``"Apache-2.0"`` / ``"MIT"`` / …)
``citation.text``          Non-empty prose citation (pydantic already enforces it)
``known_biases``           At least one entry; each non-empty string
``intended_use``           Non-empty string describing the card's intended use
``out_of_scope_use``       Non-empty string listing disallowed uses
=========================  ======================================================

The check is **pure**: no IO, no network. Callers can run it on fixture
cards for tests, on every shipped card at registry load time, or on a
single card inside GUI callbacks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from openpathai.models.cards import ModelCard

__all__ = [
    "CardIssue",
    "CardIssueCode",
    "validate_card",
]


CardIssueCode = Literal[
    "training_data_missing",
    "license_missing",
    "citation_missing",
    "known_biases_missing",
    "intended_use_missing",
    "out_of_scope_use_missing",
]
"""Stable machine-readable issue codes emitted by :func:`validate_card`."""


@dataclass(frozen=True, slots=True)
class CardIssue:
    """Structured report of one contract violation.

    Attributes
    ----------
    code:
        Stable machine-readable id — safe to branch on in callers.
    field:
        Dotted path to the offending attribute on :class:`ModelCard`.
    message:
        Human-readable explanation. Usable verbatim in the GUI banner.
    """

    code: CardIssueCode
    field: str
    message: str


def _blank(text: str | None) -> bool:
    return text is None or not text.strip()


def validate_card(card: ModelCard) -> list[CardIssue]:
    """Return every contract violation on ``card``.

    An empty list means the card is safe to expose. Callers should treat
    non-empty output as a *load-time* failure (for the registry) or a
    *greyed-out* GUI treatment (for the Models tab).
    """
    issues: list[CardIssue] = []

    if _blank(card.training_data):
        issues.append(
            CardIssue(
                code="training_data_missing",
                field="training_data",
                message=(
                    "Model card must state the corpus the weights were trained on"
                    " (set `training_data:` in the YAML)."
                ),
            )
        )
    if _blank(card.source.license):
        issues.append(
            CardIssue(
                code="license_missing",
                field="source.license",
                message="Model card must state the weight licence (set `source.license:`).",
            )
        )
    # pydantic's ``min_length=1`` already blocks fully empty citation text, but a
    # whitespace-only value slips through — catch it here for completeness.
    if _blank(card.citation.text):
        issues.append(
            CardIssue(
                code="citation_missing",
                field="citation.text",
                message="Model card must state a citation (set `citation.text:`).",
            )
        )
    if not card.known_biases or any(_blank(entry) for entry in card.known_biases):
        issues.append(
            CardIssue(
                code="known_biases_missing",
                field="known_biases",
                message=(
                    "Model card must list at least one known bias"
                    " (set `known_biases:` to a non-empty list)."
                ),
            )
        )
    if _blank(card.intended_use):
        issues.append(
            CardIssue(
                code="intended_use_missing",
                field="intended_use",
                message=(
                    "Model card must describe its intended use (set `intended_use:` in the YAML)."
                ),
            )
        )
    if _blank(card.out_of_scope_use):
        issues.append(
            CardIssue(
                code="out_of_scope_use_missing",
                field="out_of_scope_use",
                message=(
                    "Model card must list out-of-scope uses (set `out_of_scope_use:` in the YAML)."
                ),
            )
        )
    return issues
