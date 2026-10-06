from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_monitoring_service, get_user_service
from app.api.routes.monitor import router
from app.infrastructure.observability import InMemoryObservability
from app.services.monitoring_service import MonitoringService


def test_monitor_validation_ownership_and_numeric_serialization():
    collector = InMemoryObservability()
    owner, other = str(uuid4()), str(uuid4())
    with collector.turn("trace", owner, "same"):
        collector.classify("blocked", "prompt_injection")
    users = MagicMock()
    users.exists = AsyncMock(return_value=True)
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_monitoring_service] = lambda: MonitoringService(
        collector
    )
    app.dependency_overrides[get_user_service] = lambda: users
    with TestClient(app) as client:
        assert client.get("/api/monitor").status_code == 422
        assert (
            client.get("/api/monitor", headers={"X-User-ID": "bad"}).status_code == 422
        )
        response = client.get("/api/monitor", headers={"X-User-ID": owner})
        assert response.status_code == 200
        body = response.json()
        assert body["summary"]["blocked"] == 1
        assert body["summary"]["usage"]["known_cost_usd"] == 0
        assert "user_id" not in body["turns"][0]
        assert (
            client.get("/api/monitor", headers={"X-User-ID": other}).json()["turns"]
            == []
        )
        users.exists.return_value = False
        assert (
            client.get("/api/monitor", headers={"X-User-ID": owner}).status_code == 404
        )
