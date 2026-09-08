import importlib
import sys
from collections.abc import Generator
from pathlib import Path
from types import ModuleType

import pytest
from fastapi.testclient import TestClient

from app.infrastructure import paths


@pytest.fixture
def main_module(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[ModuleType]:
    frontend = tmp_path / "frontend" / "dist"
    frontend.mkdir(parents=True)
    (frontend / "index.html").write_text(
        "<!doctype html><title>Assessor.IA</title>", encoding="utf-8"
    )
    (frontend / "asset.txt").write_text("static asset", encoding="utf-8")

    monkeypatch.setattr(paths, "FRONTEND", frontend)
    sys.modules.pop("app.main", None)
    module = importlib.import_module("app.main")

    try:
        yield module
    finally:
        sys.modules.pop("app.main", None)


@pytest.fixture
def client(main_module: ModuleType) -> Generator[TestClient]:
    test_client = TestClient(main_module.app)
    try:
        yield test_client
    finally:
        test_client.close()


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "Assessor.IA API is up and running!"}


def test_root_serves_compiled_frontend(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "<title>Assessor.IA</title>" in response.text


def test_static_assets_are_served(client: TestClient) -> None:
    response = client.get("/asset.txt")

    assert response.status_code == 200
    assert response.text == "static asset"


def test_openapi_describes_chat_endpoint(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/api/chat/{session_id}" in response.json()["paths"]
    assert "/api/profile" in response.json()["paths"]
    assert "/api/session/{session_id}/finalize" in response.json()["paths"]
