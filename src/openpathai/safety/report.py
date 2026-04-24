"""Deterministic PDF rendering of a single :class:`AnalysisResult`.

Design notes
------------

* **Why ReportLab?** Pure-Python, permissive BSD licence, no native
  toolchain. We lazy-import it inside :func:`render_pdf` so
  ``import openpathai.safety`` stays cheap when the CLI only cares
  about borderline decisioning.
* **Why not a bundled TTF?** ReportLab's four Type-1 standard fonts
  (Helvetica, Times-Roman, Courier, Symbol) are mandated by the PDF
  spec itself — every reader draws them byte-identically, so we get
  cross-platform stability without shipping a 700 kB font file.
  Revisit if a pathologist asks for a non-ASCII glyph.
* **Determinism contract.** Two calls to :func:`render_pdf` with the
  same :class:`AnalysisResult` produce byte-identical PDFs. ReportLab
  stamps the document creation date; we pin it from
  ``result.timestamp`` so tests can fix time. PHI is never written:
  the report only surfaces :attr:`AnalysisResult.image_sha256`, the
  optional :attr:`AnalysisResult.image_caption`, and the model-card
  metadata.
"""

from __future__ import annotations

import io
from importlib import util as importlib_util
from pathlib import Path

from openpathai.safety.model_card import validate_card
from openpathai.safety.result import AnalysisResult

__all__ = [
    "ReportRenderError",
    "render_pdf",
]

_PAGE_MARGIN = 48  # points (2/3")
_SECTION_GAP = 18
_BODY_FONT = "Helvetica"
_BOLD_FONT = "Helvetica-Bold"


class ReportRenderError(RuntimeError):
    """Raised when ReportLab is missing or PDF rendering fails."""


def _require_reportlab() -> None:
    if importlib_util.find_spec("reportlab") is None:
        raise ReportRenderError(
            "render_pdf requires the ReportLab extra. Install via the "
            "[gui] or [safety] optional: `uv sync --extra safety`."
        )


def _reportlab_modules() -> tuple[object, object, object]:  # pragma: no cover - thin wrapper
    _require_reportlab()
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas as _canvas

    return LETTER, ImageReader, _canvas


def _draw_header(canvas: object, width: float, y: float, result: AnalysisResult) -> float:
    can = canvas  # type: ignore[assignment]
    can.setFillColorRGB(0.08, 0.09, 0.12)  # type: ignore[attr-defined]
    can.setFont(_BOLD_FONT, 18)  # type: ignore[attr-defined]
    can.drawString(_PAGE_MARGIN, y, "OpenPathAI — Analysis Report")  # type: ignore[attr-defined]
    can.setFillColorRGB(0.35, 0.37, 0.42)  # type: ignore[attr-defined]
    can.setFont(_BODY_FONT, 10)  # type: ignore[attr-defined]
    can.drawString(  # type: ignore[attr-defined]
        _PAGE_MARGIN,
        y - 14,
        f"Generated {result.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}",
    )
    return y - 32


def _draw_kv_block(
    canvas: object,
    x: float,
    y: float,
    pairs: list[tuple[str, str]],
) -> float:
    can = canvas  # type: ignore[assignment]
    label_w = 130
    can.setFillColorRGB(0.15, 0.16, 0.2)  # type: ignore[attr-defined]
    for label, value in pairs:
        can.setFont(_BOLD_FONT, 9)  # type: ignore[attr-defined]
        can.drawString(x, y, label)  # type: ignore[attr-defined]
        can.setFont(_BODY_FONT, 9)  # type: ignore[attr-defined]
        can.drawString(x + label_w, y, value)  # type: ignore[attr-defined]
        y -= 13
    return y - 4


def _draw_wrapped(
    canvas: object,
    x: float,
    y: float,
    width: float,
    text: str,
    *,
    font: str = _BODY_FONT,
    size: float = 9,
    leading: float = 12,
) -> float:
    """Word-wrap ``text`` into ``width`` points and return final ``y``."""
    can = canvas  # type: ignore[assignment]
    can.setFont(font, size)  # type: ignore[attr-defined]
    can.setFillColorRGB(0.15, 0.16, 0.2)  # type: ignore[attr-defined]
    if not text.strip():
        return y
    words = text.split()
    line = ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if can.stringWidth(candidate, font, size) <= width:  # type: ignore[attr-defined]
            line = candidate
            continue
        can.drawString(x, y, line)  # type: ignore[attr-defined]
        y -= leading
        line = word
    if line:
        can.drawString(x, y, line)  # type: ignore[attr-defined]
        y -= leading
    return y


def _draw_borderline_banner(
    canvas: object,
    x: float,
    y: float,
    width: float,
    result: AnalysisResult,
) -> float:
    can = canvas  # type: ignore[assignment]
    decision = result.borderline.decision
    colours = {
        "positive": (0.82, 0.94, 0.83),
        "negative": (0.94, 0.82, 0.82),
        "review": (1.0, 0.92, 0.78),
    }
    border = {
        "positive": (0.24, 0.55, 0.27),
        "negative": (0.72, 0.22, 0.22),
        "review": (0.82, 0.56, 0.12),
    }[decision]
    fill = colours[decision]
    height = 42
    can.setFillColorRGB(*fill)  # type: ignore[attr-defined]
    can.setStrokeColorRGB(*border)  # type: ignore[attr-defined]
    can.setLineWidth(1)  # type: ignore[attr-defined]
    can.roundRect(x, y - height, width, height, 6, stroke=1, fill=1)  # type: ignore[attr-defined]
    can.setFillColorRGB(*border)  # type: ignore[attr-defined]
    can.setFont(_BOLD_FONT, 11)  # type: ignore[attr-defined]
    can.drawString(  # type: ignore[attr-defined]
        x + 10,
        y - 16,
        f"Decision: {decision.upper()}  ({result.borderline.band})",
    )
    can.setFillColorRGB(0.15, 0.16, 0.2)  # type: ignore[attr-defined]
    can.setFont(_BODY_FONT, 9)  # type: ignore[attr-defined]
    can.drawString(  # type: ignore[attr-defined]
        x + 10,
        y - 30,
        (
            f"Predicted class: {result.predicted_class_name}  "
            f"confidence={result.borderline.confidence:.3f}  "
            f"band=[{result.borderline.low:.2f}, {result.borderline.high:.2f}]"
        ),
    )
    return y - height - 6


def _draw_probs(
    canvas: object,
    x: float,
    y: float,
    width: float,
    result: AnalysisResult,
) -> float:
    can = canvas  # type: ignore[assignment]
    can.setFont(_BOLD_FONT, 10)  # type: ignore[attr-defined]
    can.setFillColorRGB(0.15, 0.16, 0.2)  # type: ignore[attr-defined]
    can.drawString(x, y, "Per-class probabilities")  # type: ignore[attr-defined]
    y -= 14
    bar_x = x + 150
    bar_w = width - 150 - 40
    for cp in result.probabilities:
        can.setFont(_BODY_FONT, 9)  # type: ignore[attr-defined]
        can.setFillColorRGB(0.2, 0.22, 0.26)  # type: ignore[attr-defined]
        can.drawString(x, y, cp.class_name[:24])  # type: ignore[attr-defined]
        can.setFillColorRGB(0.9, 0.91, 0.94)  # type: ignore[attr-defined]
        can.rect(bar_x, y - 2, bar_w, 10, stroke=0, fill=1)  # type: ignore[attr-defined]
        fill_w = max(0.0, min(1.0, cp.probability)) * bar_w
        can.setFillColorRGB(0.24, 0.44, 0.87)  # type: ignore[attr-defined]
        can.rect(bar_x, y - 2, fill_w, 10, stroke=0, fill=1)  # type: ignore[attr-defined]
        can.setFillColorRGB(0.15, 0.16, 0.2)  # type: ignore[attr-defined]
        can.drawString(bar_x + bar_w + 6, y, f"{cp.probability:.3f}")  # type: ignore[attr-defined]
        y -= 14
    return y - 4


def _draw_image(
    canvas: object,
    image_reader_cls: object,
    x: float,
    y: float,
    width: float,
    height: float,
    png_bytes: bytes,
) -> None:
    if not png_bytes:
        return
    can = canvas  # type: ignore[assignment]
    reader = image_reader_cls(io.BytesIO(png_bytes))  # type: ignore[misc]
    can.drawImage(  # type: ignore[attr-defined]
        reader,
        x,
        y - height,
        width=width,
        height=height,
        preserveAspectRatio=True,
        mask="auto",
    )


def _draw_model_card_snippet(
    canvas: object,
    x: float,
    y: float,
    width: float,
    result: AnalysisResult,
) -> float:
    from openpathai.models import default_model_registry

    can = canvas  # type: ignore[assignment]
    can.setFont(_BOLD_FONT, 10)  # type: ignore[attr-defined]
    can.setFillColorRGB(0.15, 0.16, 0.2)  # type: ignore[attr-defined]
    can.drawString(x, y, "Model card")  # type: ignore[attr-defined]
    y -= 14

    reg = default_model_registry()
    model_card = None
    issues_line = ""
    try:
        model_card = reg.get(result.model_name)
    except KeyError:
        # Card may have been greyed out; try the invalid bucket to still
        # report something useful.
        try:
            model_card = reg.invalid_card(result.model_name)
            issues = reg.invalid_issues(result.model_name)
            issues_line = "; ".join(sorted({i.code for i in issues}))
        except KeyError:
            pass

    if model_card is None:
        can.setFont(_BODY_FONT, 9)  # type: ignore[attr-defined]
        can.drawString(x, y, f"(model card {result.model_name!r} not registered)")  # type: ignore[attr-defined]
        return y - 14

    info = [
        ("Name:", model_card.name),
        ("Display:", model_card.display_name),
        ("Licence:", model_card.source.license),
        ("Citation:", model_card.citation.text),
    ]
    y = _draw_kv_block(canvas, x, y, info)
    if issues_line:
        y = _draw_wrapped(canvas, x, y, width, f"Card issues: {issues_line}", font=_BOLD_FONT)
        y -= 2
    if model_card.training_data:
        y = _draw_wrapped(canvas, x, y, width, f"Training data: {model_card.training_data}")
    if model_card.intended_use:
        y = _draw_wrapped(canvas, x, y, width, f"Intended use: {model_card.intended_use}")
    if model_card.out_of_scope_use:
        y = _draw_wrapped(canvas, x, y, width, f"Out-of-scope use: {model_card.out_of_scope_use}")
    if model_card.known_biases:
        biases = "; ".join(model_card.known_biases)
        y = _draw_wrapped(canvas, x, y, width, f"Known biases: {biases}")

    # Re-run the contract so the PDF reflects the live state.
    live_issues = validate_card(model_card)
    if live_issues:
        codes = ", ".join(sorted({i.code for i in live_issues}))
        y = _draw_wrapped(
            canvas,
            x,
            y,
            width,
            f"Contract violations on this card: {codes}",
            font=_BOLD_FONT,
        )
    return y


def _assert_no_path_leak(result: AnalysisResult) -> None:
    """Guard: PHI-style filesystem paths must never appear in a PDF.

    We scan the caption (the only free-text field the user supplies
    directly) and the model-name / explainer-name strings. Everything
    else on the result is either structured metadata or bytes.
    """
    for value in (result.image_caption, result.model_name, result.explainer_name):
        if "/Users/" in value or "/home/" in value:
            raise ReportRenderError(
                "PDF render refused: input contained a filesystem path fragment "
                "(/Users/ or /home/). Strip the path before building AnalysisResult."
            )


def render_pdf(result: AnalysisResult, out_path: str | Path) -> Path:
    """Render a PDF report for ``result`` to ``out_path``.

    Returns the :class:`Path` that was written. Creates parent directories
    if needed.
    """
    _assert_no_path_leak(result)
    LETTER, ImageReader, canvas_mod = _reportlab_modules()  # type: ignore[misc]  # noqa: N806

    out = Path(out_path).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)

    page_w, page_h = LETTER  # type: ignore[misc]
    # ``invariant=True`` tells ReportLab to strip every source of
    # non-determinism (random document ID, wall-clock creationDate) so the
    # bytes depend only on the content + the pinned creation date below.
    can = canvas_mod.Canvas(str(out), pagesize=LETTER, invariant=True)  # type: ignore[attr-defined]
    ts = result.timestamp.strftime("D:%Y%m%d%H%M%S+00'00'")
    can.setAuthor("OpenPathAI")  # type: ignore[attr-defined]
    can.setCreator("OpenPathAI safety.report")  # type: ignore[attr-defined]
    can.setTitle(f"OpenPathAI report — {result.model_name}")  # type: ignore[attr-defined]
    can.setSubject(f"Analysis of image SHA-256 {result.image_sha256[:16]}…")  # type: ignore[attr-defined]
    can._doc.info.creationDate = ts  # type: ignore[attr-defined]
    can._doc.info.modDate = ts  # type: ignore[attr-defined]
    can._doc.info.invariant = True  # type: ignore[attr-defined]

    y = page_h - _PAGE_MARGIN
    y = _draw_header(can, page_w, y, result)
    y = _draw_kv_block(
        can,
        _PAGE_MARGIN,
        y,
        [
            ("Model:", result.model_name),
            ("Explainer:", result.explainer_name),
            ("Image SHA-256:", result.image_sha256),
            ("Manifest hash:", result.manifest_hash or "(not recorded)"),
            ("Caption:", result.image_caption or "(none)"),
        ],
    )
    y -= _SECTION_GAP

    # Side-by-side thumbnail + overlay. Max 220x220 pts each.
    img_w = (page_w - 2 * _PAGE_MARGIN - 20) / 2
    img_h = img_w
    _draw_image(can, ImageReader, _PAGE_MARGIN, y, img_w, img_h, result.thumbnail_png)
    _draw_image(can, ImageReader, _PAGE_MARGIN + img_w + 20, y, img_w, img_h, result.overlay_png)
    if result.thumbnail_png or result.overlay_png:
        y -= img_h + _SECTION_GAP

    y = _draw_borderline_banner(can, _PAGE_MARGIN, y, page_w - 2 * _PAGE_MARGIN, result)
    y -= _SECTION_GAP
    y = _draw_probs(can, _PAGE_MARGIN, y, page_w - 2 * _PAGE_MARGIN, result)
    y -= _SECTION_GAP
    y = _draw_model_card_snippet(can, _PAGE_MARGIN, y, page_w - 2 * _PAGE_MARGIN, result)
    y -= _SECTION_GAP
    can.setFont(_BOLD_FONT, 10)  # type: ignore[attr-defined]
    can.setFillColorRGB(0.72, 0.22, 0.22)  # type: ignore[attr-defined]
    can.drawString(_PAGE_MARGIN, y, "Disclaimer")  # type: ignore[attr-defined]
    y -= 12
    _draw_wrapped(
        can,
        _PAGE_MARGIN,
        y,
        page_w - 2 * _PAGE_MARGIN,
        AnalysisResult.disclaimer(),
    )

    can.showPage()  # type: ignore[attr-defined]
    can.save()  # type: ignore[attr-defined]
    return out
