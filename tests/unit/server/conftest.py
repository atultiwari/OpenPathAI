"""Shared fixtures for the Phase-19 FastAPI tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from openpathai.server.app import create_app
from openpathai.server.config import ServerSettings

TEST_TOKEN = "test-token-1234567890abcdef"


@pytest.fixture
def settings(tmp_path: Path) -> ServerSettings:
    return ServerSettings(
        token=TEST_TOKEN,
        openpathai_home=tmp_path,
        pipelines_dir=tmp_path / "pipelines",
    )


@pytest.fixture
def client(settings: ServerSettings) -> Iterator[TestClient]:
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_TOKEN}"}
