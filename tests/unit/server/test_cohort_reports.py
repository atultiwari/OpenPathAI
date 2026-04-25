"""Phase 21 refinement #4 — cohort QC HTML/PDF download."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient


def _seed_cohort(client: TestClient, headers: dict[str, str], tmp_path: Path) -> str:
    pool = tmp_path / "cohort-src"
    pool.mkdir()
    # Two synthetic 1x1 PNGs registered as slides for the QC pipeline.
    from PIL import Image

    for n in range(2):
        Image.new("RGB", (8, 8), color=(n * 50, 100, 100)).save(pool / f"s_{n}.png")
    response = client.post(
        "/v1/cohorts",
        headers=headers,
        json={"id": "qc_smoke", "directory": str(pool), "pattern": "*.png"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_qc_html_is_self_contained(
    client: TestClient, auth_headers: dict[str, str], tmp_path: Path
) -> None:
    cid = _seed_cohort(client, auth_headers, tmp_path)
    response = client.get(f"/v1/cohorts/{cid}/qc.html", headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    body = response.text
    assert "<!doctype html>" in body
    assert "QC report" in body
    assert "pass" in body and "warn" in body and "fail" in body


def test_qc_summary_links_to_html_and_pdf(
    client: TestClient, auth_headers: dict[str, str], tmp_path: Path
) -> None:
    cid = _seed_cohort(client, auth_headers, tmp_path)
    response = client.post(f"/v1/cohorts/{cid}/qc", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["html_url"].endswith("/qc.html")
    assert body["pdf_url"].endswith("/qc.pdf")
    assert "summary" in body and "slide_findings" in body


def test_qc_pdf_when_safety_extra_present(
    client: TestClient, auth_headers: dict[str, str], tmp_path: Path
) -> None:
    pytest.importorskip("reportlab")
    cid = _seed_cohort(client, auth_headers, tmp_path)
    response = client.get(f"/v1/cohorts/{cid}/qc.pdf", headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_qc_html_404_for_missing_cohort(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.get("/v1/cohorts/missing/qc.html", headers=auth_headers)
    assert response.status_code == 404
