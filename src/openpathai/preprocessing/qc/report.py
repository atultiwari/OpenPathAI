"""HTML + PDF renderers for :class:`CohortQCReport`.

Both renderers are deterministic: inputs in → byte-identical output
out. HTML uses inline CSS (no external assets) so the file is
self-contained; PDF reuses the Phase 7 ReportLab ``invariant=True``
mode and pins the PDF ``creationDate`` from
``report.generated_at_utc``.
"""

from __future__ import annotations

import html
from datetime import UTC, datetime
from importlib import util as importlib_util
from pathlib import Path

from openpathai.preprocessing.qc.aggregate import CohortQCReport, SlideQCReport

__all__ = [
    "QCReportRenderError",
    "render_html",
    "render_pdf",
]


class QCReportRenderError(RuntimeError):
    """Raised when ReportLab is missing or rendering fails."""


# --------------------------------------------------------------------------- #
# HTML
# --------------------------------------------------------------------------- #


_HTML_HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>OpenPathAI — Cohort QC report</title>
<style>
body { font-family: -apple-system, Helvetica, Arial, sans-serif;
       margin: 2em; color: #1a1b20; }
h1 { margin-bottom: 0.3em; }
.meta { color: #7a7c83; font-size: 0.9em; margin-bottom: 2em; }
.summary { margin: 1em 0 2em 0; padding: 0.8em 1em; background: #f4f5f8;
           border-radius: 6px; display: inline-block; }
table { border-collapse: collapse; width: 100%; }
th, td { padding: 0.4em 0.7em; border-bottom: 1px solid #e4e5ea;
         text-align: left; vertical-align: top; }
th { background: #fafbfd; font-weight: 600; }
tr.pass   { background: #ffffff; }
tr.warn   { background: #fffaed; }
tr.fail   { background: #fff2f2; }
.badge { display: inline-block; width: 1.1em; text-align: center; }
code { background: #f4f5f8; padding: 0.1em 0.3em; border-radius: 3px; }
.disclaimer { margin-top: 2em; padding: 0.8em 1em; background: #fff7e6;
              border: 1px solid #f0d79a; border-radius: 6px;
              font-size: 0.9em; color: #8a5a16; }
</style>
</head>
<body>
"""


_HTML_FOOT = """
<div class="disclaimer">
  OpenPathAI produces research-grade QC findings and is NOT a medical
  device. QC flags are advisory — human expert review is required
  before any diagnostic or training decision.
</div>
</body>
</html>
"""


def _slide_row_html(slide: SlideQCReport) -> str:
    worst = slide.severity
    tr_class = "pass" if slide.passed else worst
    badges = " ".join(f.badge for f in slide.qc_findings)
    tooltip_lines = [f"{f.check}: {f.message}" for f in slide.qc_findings]
    tooltip = html.escape("\n".join(tooltip_lines), quote=True)
    return (
        f'<tr class="{tr_class}">'
        f"<td><code>{html.escape(slide.slide_id)}</code></td>"
        f"<td>{html.escape(worst.upper())}</td>"
        f'<td><span class="badge" title="{tooltip}">{badges}</span></td>'
        "</tr>"
    )


def render_html(report: CohortQCReport, out_path: str | Path) -> Path:
    """Render ``report`` to a self-contained HTML file.

    Returns the :class:`Path` that was written. Creates parent
    directories if needed.
    """
    out = Path(out_path).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)

    summary = report.summary()
    rows = "\n".join(_slide_row_html(s) for s in report.slide_findings)

    body = (
        f"{_HTML_HEAD}"
        f"<h1>Cohort QC report — {html.escape(report.cohort_id)}</h1>"
        f'<div class="meta">Generated '
        f"{html.escape(report.generated_at_utc)}</div>"
        f'<div class="summary">'
        f"<strong>{summary['pass']}</strong> passed &nbsp;·&nbsp; "
        f"<strong>{summary['warn']}</strong> warnings &nbsp;·&nbsp; "
        f"<strong>{summary['fail']}</strong> failures"
        f"</div>"
        "<table>"
        "<thead><tr><th>Slide</th><th>Severity</th>"
        "<th>Findings</th></tr></thead><tbody>"
        f"{rows}"
        "</tbody></table>"
        f"{_HTML_FOOT}"
    )

    out.write_text(body, encoding="utf-8")
    return out


# --------------------------------------------------------------------------- #
# PDF (ReportLab — lazy-imported)
# --------------------------------------------------------------------------- #


def _require_reportlab() -> None:
    if importlib_util.find_spec("reportlab") is None:
        raise QCReportRenderError(
            "render_pdf requires ReportLab. Install via the [safety] "
            "optional extra: `uv sync --extra safety`."
        )


def _reportlab_modules() -> tuple[object, object]:  # pragma: no cover - wrapper
    _require_reportlab()
    from reportlab.lib.pagesizes import LETTER
    from reportlab.pdfgen import canvas as _canvas

    return LETTER, _canvas


def _parse_timestamp(generated_at_utc: str) -> datetime:
    try:
        return datetime.fromisoformat(generated_at_utc)
    except ValueError:
        return datetime.now(UTC)


def render_pdf(report: CohortQCReport, out_path: str | Path) -> Path:
    """Render ``report`` to a deterministic PDF via ReportLab."""
    LETTER, canvas_mod = _reportlab_modules()  # type: ignore[misc]  # noqa: N806

    out = Path(out_path).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    _page_w, page_h = LETTER  # type: ignore[misc]  # width is unused (single-column layout)

    can = canvas_mod.Canvas(str(out), pagesize=LETTER, invariant=True)  # type: ignore[attr-defined]
    ts = _parse_timestamp(report.generated_at_utc).strftime("D:%Y%m%d%H%M%S+00'00'")
    can.setAuthor("OpenPathAI")  # type: ignore[attr-defined]
    can.setCreator("OpenPathAI preprocessing.qc.report")  # type: ignore[attr-defined]
    can.setTitle(f"OpenPathAI cohort QC — {report.cohort_id}")  # type: ignore[attr-defined]
    can.setSubject("Cohort QC report")  # type: ignore[attr-defined]
    can._doc.info.creationDate = ts  # type: ignore[attr-defined]
    can._doc.info.modDate = ts  # type: ignore[attr-defined]
    can._doc.info.invariant = True  # type: ignore[attr-defined]

    margin = 48
    y = page_h - margin
    can.setFont("Helvetica-Bold", 18)  # type: ignore[attr-defined]
    can.setFillColorRGB(0.08, 0.09, 0.12)  # type: ignore[attr-defined]
    can.drawString(margin, y, f"Cohort QC report — {report.cohort_id}")  # type: ignore[attr-defined]
    y -= 18
    can.setFont("Helvetica", 10)  # type: ignore[attr-defined]
    can.setFillColorRGB(0.35, 0.37, 0.42)  # type: ignore[attr-defined]
    can.drawString(margin, y, f"Generated {report.generated_at_utc}")  # type: ignore[attr-defined]
    y -= 22

    summary = report.summary()
    can.setFont("Helvetica-Bold", 11)  # type: ignore[attr-defined]
    can.setFillColorRGB(0.15, 0.16, 0.2)  # type: ignore[attr-defined]
    can.drawString(  # type: ignore[attr-defined]
        margin,
        y,
        f"Summary   pass={summary['pass']}   warn={summary['warn']}   fail={summary['fail']}",
    )
    y -= 24

    can.setFont("Helvetica-Bold", 10)  # type: ignore[attr-defined]
    can.drawString(margin, y, "Slide id")  # type: ignore[attr-defined]
    can.drawString(margin + 250, y, "Severity")  # type: ignore[attr-defined]
    can.drawString(margin + 340, y, "Findings")  # type: ignore[attr-defined]
    y -= 14
    can.setFont("Helvetica", 9)  # type: ignore[attr-defined]

    for slide in report.slide_findings:
        if y < margin + 40:
            can.showPage()  # type: ignore[attr-defined]
            y = page_h - margin
            can.setFont("Helvetica", 9)  # type: ignore[attr-defined]
        can.setFillColorRGB(0.15, 0.16, 0.2)  # type: ignore[attr-defined]
        can.drawString(margin, y, slide.slide_id[:40])  # type: ignore[attr-defined]
        can.drawString(margin + 250, y, slide.severity.upper())  # type: ignore[attr-defined]
        detail = ", ".join(f"{f.check}={'ok' if f.passed else 'fail'}" for f in slide.qc_findings)
        can.drawString(margin + 340, y, detail[:60])  # type: ignore[attr-defined]
        y -= 12

    y -= 18
    can.setFont("Helvetica", 8)  # type: ignore[attr-defined]
    can.setFillColorRGB(0.72, 0.22, 0.22)  # type: ignore[attr-defined]
    can.drawString(  # type: ignore[attr-defined]
        margin,
        y,
        "OpenPathAI QC is research-grade and NOT a medical device.",
    )

    can.showPage()  # type: ignore[attr-defined]
    can.save()  # type: ignore[attr-defined]
    return out
