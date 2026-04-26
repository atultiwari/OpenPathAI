"""Phase 21.7 chunk D — /v1/extras status route."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_extras_lists_every_documented_extra(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.get("/v1/extras", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    items = body["items"]
    names = {item["name"] for item in items}
    expected = {
        "server",
        "data",
        "train",
        "wsi",
        "explain",
        "safety",
        "kaggle",
        "gui",
        "mlflow",
    }
    assert expected.issubset(names)
    for item in items:
        assert item["install_cmd"].startswith("uv sync --extra ")
        assert item["description"]
        assert isinstance(item["installed"], bool)


def test_extras_installed_flag_reflects_real_imports(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """The ``server`` extra must always be installed when this test runs
    (the server itself depends on fastapi). We don't assert anything
    about the optional extras (CI matrix decides which are present)."""
    response = client.get("/v1/extras", headers=auth_headers)
    items = response.json()["items"]
    server = next(i for i in items if i["name"] == "server")
    assert server["installed"] is True


def test_extras_requires_auth(client: TestClient) -> None:
    assert client.get("/v1/extras").status_code in (401, 403)


def test_extras_install_commands_are_unique(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    items = client.get("/v1/extras", headers=auth_headers).json()["items"]
    cmds = [i["install_cmd"] for i in items]
    assert len(set(cmds)) == len(cmds), "duplicate install_cmd entries"


def test_extras_train_describes_lightning(client: TestClient, auth_headers: dict[str, str]) -> None:
    items = client.get("/v1/extras", headers=auth_headers).json()["items"]
    train = next(i for i in items if i["name"] == "train")
    assert "lightning" in train["description"].lower() or "torch" in train["description"].lower()
