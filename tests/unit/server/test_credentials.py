"""Phase 21.5 chunk C — /v1/credentials/huggingface routes."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from openpathai.config import hf


@pytest.fixture(autouse=True)
def isolated_credentials(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    """The conftest fixture already sets openpathai_home to tmp_path,
    but the HF resolver reads OPENPATHAI_HOME from the env. Mirror it
    here and clear the two env-var fallbacks so each test starts from
    a known empty state."""
    monkeypatch.setenv("OPENPATHAI_HOME", str(settings.openpathai_home))
    monkeypatch.delenv(hf.ENV_HF_TOKEN, raising=False)
    monkeypatch.delenv(hf.ENV_HF_HUB_TOKEN, raising=False)


def test_get_status_returns_none_when_unconfigured(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.get("/v1/credentials/huggingface", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body == {"present": False, "source": "none", "token_preview": None}


def test_put_persists_redacts_and_round_trips(
    client: TestClient, auth_headers: dict[str, str], settings
) -> None:
    response = client.put(
        "/v1/credentials/huggingface",
        headers=auth_headers,
        json={"token": "hf_supersecret_abcd"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["saved"] is True
    secrets_path = Path(body["secrets_path"])
    assert secrets_path.is_file()
    # Stored on the server-controlled home, not echoed back as a path
    # under /tmp from the *client*.
    assert secrets_path.parent == settings.openpathai_home
    assert body["status"] == {
        "present": True,
        "source": "settings",
        "token_preview": "…abcd",
    }

    # GET reflects the new state, also redacted.
    status = client.get("/v1/credentials/huggingface", headers=auth_headers).json()
    assert status == {
        "present": True,
        "source": "settings",
        "token_preview": "…abcd",
    }

    # The plaintext token never appears in either response payload.
    assert "hf_supersecret_abcd" not in response.text
    assert (
        "hf_supersecret_abcd"
        not in client.get("/v1/credentials/huggingface", headers=auth_headers).text
    )


def test_put_rejects_empty_token(client: TestClient, auth_headers: dict[str, str]) -> None:
    # Empty fails validation at the pydantic layer (min_length=1).
    response = client.put(
        "/v1/credentials/huggingface",
        headers=auth_headers,
        json={"token": ""},
    )
    assert response.status_code == 422


def test_put_rejects_whitespace_only_token(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    # Whitespace-only passes pydantic min_length but is rejected by
    # set_token; surfaced as 422.
    response = client.put(
        "/v1/credentials/huggingface",
        headers=auth_headers,
        json={"token": "   "},
    )
    assert response.status_code == 422


def test_delete_clears_token(client: TestClient, auth_headers: dict[str, str]) -> None:
    client.put(
        "/v1/credentials/huggingface",
        headers=auth_headers,
        json={"token": "stored_token_xyz"},
    )
    response = client.delete("/v1/credentials/huggingface", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["cleared"] is True
    assert body["status"]["present"] is False
    # Second DELETE is a no-op.
    second = client.delete("/v1/credentials/huggingface", headers=auth_headers)
    assert second.json()["cleared"] is False


def test_test_endpoint_reports_no_token_when_unconfigured(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post("/v1/credentials/huggingface/test", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["reason"] == "no_token_configured"
    assert body["status"]["present"] is False


def test_settings_file_wins_over_env(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(hf.ENV_HF_TOKEN, "from-env")
    # Without saved settings, source is env.
    body = client.get("/v1/credentials/huggingface", headers=auth_headers).json()
    assert body["source"] == "env_hf_token"

    # Save a settings token — that wins.
    client.put(
        "/v1/credentials/huggingface",
        headers=auth_headers,
        json={"token": "from-settings"},
    )
    body = client.get("/v1/credentials/huggingface", headers=auth_headers).json()
    assert body["source"] == "settings"
    assert body["token_preview"] == "…ings"


def test_credentials_routes_require_auth(client: TestClient) -> None:
    assert client.get("/v1/credentials/huggingface").status_code in (401, 403)
    assert client.put("/v1/credentials/huggingface", json={"token": "x"}).status_code in (401, 403)
    assert client.delete("/v1/credentials/huggingface").status_code in (401, 403)
    assert client.post("/v1/credentials/huggingface/test").status_code in (401, 403)
