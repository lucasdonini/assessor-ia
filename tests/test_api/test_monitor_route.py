from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.auth import get_auth_service
from app.api.dependencies import get_monitor_access, get_monitor_service
from app.api.routes.auth import router as auth_router
from app.api.routes.monitor import router
from app.application.models.google_identity import WebSession
from app.infrastructure.observability import TurnTelemetry
from app.services.auth_service import AuthenticationError
from app.services.monitor_service import MonitorAccess, MonitorService


def test_monitor_auth_scope_contract_and_account_capability():
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    auth = AsyncMock()
    auth.session.return_value = WebSession(
        user_id=uuid4(),
        subject="google-subject",
        email="Admin@Example.com",
        csrf="csrf",
    )
    store = TurnTelemetry(lambda _: MagicMock())
    service = MonitorService(store)
    app.dependency_overrides[get_auth_service] = lambda: auth
    app.dependency_overrides[get_monitor_access] = lambda: MonitorAccess(
        ("admin@example.com",)
    )
    app.dependency_overrides[get_monitor_service] = lambda: service
    with TestClient(app) as client:
        response = client.get("/api/monitor")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["scope"] == "operator_global"
        assert response.json()["slo"]["ok"] is None
        assert client.get("/api/auth/me").json()["can_monitor"] is True
        assert "/api/monitor" in client.get("/openapi.json").json()["paths"]
        auth.session.return_value = auth.session.return_value.model_copy(
            update={"email": "other@example.com"}
        )
        assert (
            client.get(
                "/api/monitor", headers={"X-User-Email": "admin@example.com"}
            ).status_code
            == 403
        )
        assert client.get("/api/auth/me").json()["can_monitor"] is False
        auth.session.side_effect = AuthenticationError()
        assert client.get("/api/monitor").status_code == 401
