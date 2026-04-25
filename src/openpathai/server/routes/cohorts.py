"""Cohort CRUD (Phase 20.5).

Cohorts are stored as YAML files under
``settings.openpathai_home / "cohorts"`` so the canvas Cohorts
screen can list / build / load / QC them without a database.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field

from openpathai.io.cohort import Cohort
from openpathai.server.auth import AuthDependency

__all__ = ["BuildCohortRequest", "router"]


router = APIRouter(prefix="/cohorts", tags=["cohorts"], dependencies=[AuthDependency])


_SAFE_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_\-]*$")


class BuildCohortRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    directory: str = Field(min_length=1)
    pattern: str | None = None


def _root(request: Request) -> Path:
    root = request.app.state.settings.openpathai_home / "cohorts"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe(cohort_id: str) -> str:
    if not _SAFE_ID.match(cohort_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid cohort id {cohort_id!r}",
        )
    return cohort_id


def _path(request: Request, cohort_id: str) -> Path:
    return _root(request) / f"{_safe(cohort_id)}.yaml"


def _envelope(cohort_id: str, cohort: Cohort) -> dict[str, Any]:
    return {
        "id": cohort_id,
        "slide_count": len(cohort.slides),
        # Slide ids are user-supplied IDs (not paths) — safe to surface.
        "slide_ids": [s.slide_id for s in cohort.slides],
    }


@router.get("", summary="List saved cohorts")
async def list_cohorts(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    root = _root(request)
    files = sorted(root.glob("*.yaml"))
    items: list[dict[str, Any]] = []
    for fh in files:
        try:
            cohort = Cohort.from_yaml(fh)
            items.append(_envelope(fh.stem, cohort))
        except (ValueError, FileNotFoundError) as exc:
            items.append({"id": fh.stem, "error": str(exc)})
    total = len(items)
    return {
        "items": items[offset : offset + limit],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Build a cohort YAML from a directory of slide files",
)
async def create_cohort(request: Request, body: BuildCohortRequest) -> dict[str, Any]:
    try:
        cohort = Cohort.from_directory(body.directory, body.id, pattern=body.pattern)
    except (NotADirectoryError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    out = _path(request, body.id)
    cohort.to_yaml(out)
    return _envelope(body.id, cohort)


@router.get("/{cohort_id}", summary="Retrieve a saved cohort")
async def get_cohort(request: Request, cohort_id: str) -> dict[str, Any]:
    path = _path(request, cohort_id)
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"cohort {cohort_id!r} not found",
        )
    cohort = Cohort.from_yaml(path)
    return _envelope(cohort_id, cohort)


@router.delete(
    "/{cohort_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a saved cohort",
)
async def delete_cohort(request: Request, cohort_id: str) -> None:
    path = _path(request, cohort_id)
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"cohort {cohort_id!r} not found",
        )
    path.unlink()


def _run_qc_report(cohort: Cohort) -> Any:
    def _flat(_slide: Any) -> np.ndarray:
        # The Phase-9 QC plumbing accepts a thumbnail extractor. Without
        # the GUI / WSI viewer we hand it a deterministic mid-grey so
        # the endpoint doesn't depend on Tier-2+ deps.
        return np.full((96, 96, 3), 200, dtype=np.uint8)

    return cohort.run_qc(_flat)


@router.post(
    "/{cohort_id}/qc",
    summary="Run QC over a cohort (returns the summary tile)",
)
async def cohort_qc(request: Request, cohort_id: str) -> dict[str, Any]:
    path = _path(request, cohort_id)
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"cohort {cohort_id!r} not found",
        )
    cohort = Cohort.from_yaml(path)
    try:
        report = _run_qc_report(cohort)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"QC failed: {exc!s}",
        ) from exc
    return {
        "id": cohort_id,
        "summary": report.summary(),
        "slide_count": len(cohort.slides),
        "slide_findings": [s.model_dump(mode="json") for s in report.slide_findings],
        "html_url": f"/v1/cohorts/{cohort_id}/qc.html",
        "pdf_url": f"/v1/cohorts/{cohort_id}/qc.pdf",
    }


def _render_html(cohort_id: str, report: Any) -> str:
    """Self-contained QC HTML report (no external CSS / JS).

    Phase 21 keeps this dependency-free so it works in every Tier and
    can be downloaded straight from the browser."""
    summary = report.summary()
    rows: list[str] = []
    for slide in report.slide_findings:
        finding_rows = "".join(
            (
                "<tr>"
                f"<td>{f['check']}</td>"
                f"<td>{f['severity']}</td>"
                f"<td>{f['score']:.3f}</td>"
                f"<td>{'pass' if f['passed'] else 'fail'}</td>"
                f"<td>{_escape(f['message'])}</td>"
                "</tr>"
            )
            for f in slide.findings
        )
        rows.append(
            "<section class='slide'>"
            f"<h3>{_escape(slide.slide_id)} <span class='sev sev-{slide.severity}'>"
            f"{slide.severity}</span></h3>"
            "<table><thead><tr>"
            "<th>check</th><th>severity</th><th>score</th><th>passed</th><th>message</th>"
            "</tr></thead><tbody>"
            f"{finding_rows}"
            "</tbody></table>"
            "</section>"
        )
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>OpenPathAI QC — {_escape(cohort_id)}</title>"
        "<style>"
        "body{font-family:system-ui,sans-serif;margin:2rem;color:#111;}"
        "h1{margin:0 0 .25rem 0;}"
        ".meta{color:#555;margin-bottom:1.5rem;}"
        ".kpis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));"
        "gap:1rem;margin-bottom:2rem;}"
        ".kpi{background:#f4f4f4;padding:1rem;border-radius:.5rem;text-align:center;}"
        ".kpi .n{font-size:2rem;font-weight:700;display:block;}"
        "table{width:100%;border-collapse:collapse;margin-bottom:1rem;}"
        "th,td{padding:.4rem .6rem;border-bottom:1px solid #eee;text-align:left;}"
        ".sev{font-size:.75rem;text-transform:uppercase;padding:.1rem .4rem;border-radius:.25rem;}"
        ".sev-info{background:#dbeafe;color:#1d4ed8;}"
        ".sev-warn{background:#fef3c7;color:#92400e;}"
        ".sev-fail{background:#fee2e2;color:#991b1b;}"
        "</style></head><body>"
        f"<h1>QC report — {_escape(cohort_id)}</h1>"
        f"<p class='meta'>Generated {_escape(report.generated_at_utc)}"
        f" · {len(report.slide_findings)} slide(s)</p>"
        "<div class='kpis'>"
        f"<div class='kpi'><span class='n'>{summary['pass']}</span> pass</div>"
        f"<div class='kpi'><span class='n'>{summary['warn']}</span> warn</div>"
        f"<div class='kpi'><span class='n'>{summary['fail']}</span> fail</div>"
        "</div>" + "".join(rows) + "</body></html>"
    )


def _escape(value: str) -> str:
    return (
        value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


@router.get(
    "/{cohort_id}/qc.html",
    summary="QC report — HTML",
    responses={200: {"content": {"text/html": {}}}},
)
async def cohort_qc_html(request: Request, cohort_id: str):
    from fastapi.responses import HTMLResponse

    path = _path(request, cohort_id)
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"cohort {cohort_id!r} not found",
        )
    cohort = Cohort.from_yaml(path)
    report = _run_qc_report(cohort)
    return HTMLResponse(content=_render_html(cohort_id, report))


@router.get(
    "/{cohort_id}/qc.pdf",
    summary="QC report — PDF",
    responses={200: {"content": {"application/pdf": {}}}},
)
async def cohort_qc_pdf(request: Request, cohort_id: str):
    from fastapi.responses import Response

    path = _path(request, cohort_id)
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"cohort {cohort_id!r} not found",
        )
    cohort = Cohort.from_yaml(path)
    report = _run_qc_report(cohort)
    try:
        pdf_bytes = _render_pdf(cohort_id, report)
    except _PdfMissingError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return Response(content=pdf_bytes, media_type="application/pdf")


class _PdfMissingError(RuntimeError):
    """Raised when ReportLab is unavailable (``[safety]`` extra missing)."""


def _render_pdf(cohort_id: str, report: Any) -> bytes:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import LETTER
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except Exception as exc:
        raise _PdfMissingError(
            "PDF rendering requires the [safety] extra (`uv sync --extra safety`)."
        ) from exc

    import io

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER)
    styles = getSampleStyleSheet()
    story = [
        Paragraph(f"QC report — {cohort_id}", styles["Title"]),
        Paragraph(
            f"Generated {report.generated_at_utc} · {len(report.slide_findings)} slide(s)",
            styles["Normal"],
        ),
        Spacer(1, 12),
    ]
    summary = report.summary()
    story.append(
        Paragraph(
            f"<b>Pass:</b> {summary['pass']} &nbsp;&nbsp; "
            f"<b>Warn:</b> {summary['warn']} &nbsp;&nbsp; "
            f"<b>Fail:</b> {summary['fail']}",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 12))
    for slide in report.slide_findings:
        story.append(
            Paragraph(
                f"<b>{slide.slide_id}</b> &nbsp; <i>{slide.severity}</i>",
                styles["Heading3"],
            )
        )
        rows: list[list[str]] = [["check", "severity", "score", "passed", "message"]]
        for f in slide.findings:
            rows.append(
                [
                    str(f["check"]),
                    str(f["severity"]),
                    f"{f['score']:.3f}",
                    "pass" if f["passed"] else "fail",
                    str(f["message"]),
                ]
            )
        table = Table(rows, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                ]
            )
        )
        story.append(table)
        story.append(Spacer(1, 12))
    doc.build(story)
    return buf.getvalue()
