"""Iron rule #8 — response bodies never contain raw filesystem paths."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from openpathai.server.phi import (
    PHI_PATH_REGEX,
    hash_patient_id,
    redact_response_payload,
)

_PATH_SENTINELS = re.compile(
    r"(?:/Users/[^\s\"']+|/home/[^\s\"']+|/root/[^\s\"']+"
    r"|[A-Za-z]:\\(?![nrtbfu0v/\\\"' ])[A-Za-z0-9_][^\s\"']*)"
)


def test_no_paths_in_openapi(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert not _PATH_SENTINELS.search(response.text)


def test_no_paths_in_datasets(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/v1/datasets", headers=auth_headers)
    assert not _PATH_SENTINELS.search(response.text)


def test_no_paths_in_models(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/v1/models", headers=auth_headers)
    assert not _PATH_SENTINELS.search(response.text)


def test_no_paths_in_audit(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/v1/audit/runs", headers=auth_headers)
    assert not _PATH_SENTINELS.search(response.text)


def test_redact_response_payload_rewrites_paths() -> None:
    payload = {
        "file_paths": [
            "/Users/dr-smith/patient-42/slide.svs",
            "/home/rahul/research/slide.svs",
            "C:\\data\\cases\\CaseA.svs",
        ],
        "nested": {"where": "/Users/alice/x.tiff"},
        "keep": "just a normal string",
        "number": 42,
    }
    redacted = redact_response_payload(payload)
    text = json.dumps(redacted)
    assert not _PATH_SENTINELS.search(text)
    assert "slide.svs" in text  # basename preserved
    assert redacted["keep"] == "just a normal string"
    assert redacted["number"] == 42


def test_phi_regex_basic_matches() -> None:
    assert PHI_PATH_REGEX.search("/Users/alice/x")
    assert PHI_PATH_REGEX.search("/home/bob/y")
    assert PHI_PATH_REGEX.search("C:\\data\\cases")
    assert not PHI_PATH_REGEX.search("just text")
    # JSON escape sequences must not false-positive.
    assert not PHI_PATH_REGEX.search("is:\\nnewline")
    assert not PHI_PATH_REGEX.search("x:\\tnew")


def test_hash_patient_id_stable_and_short() -> None:
    assert hash_patient_id("pt-42").startswith("pt-")
    assert len(hash_patient_id("pt-42")) == len("pt-") + 8
    assert hash_patient_id("pt-42") == hash_patient_id("pt-42")
    assert hash_patient_id("pt-42") != hash_patient_id("pt-99")
    assert hash_patient_id("") == ""
    assert hash_patient_id(None) == ""


def test_path_containing_string_in_plain_text_field_is_redacted(tmp_path: Path) -> None:
    del tmp_path
    from openpathai.server.phi import redact_response_payload

    payload = {"message": "wrote file to /Users/dr-smith/patient-42/slide.svs"}
    redacted = redact_response_payload(payload)
    assert "/Users/dr-smith" not in redacted["message"]
    assert "slide.svs" in redacted["message"]
