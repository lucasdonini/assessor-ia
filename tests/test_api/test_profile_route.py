from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_user_context
from app.api.middleware.exception_handler import register_exception_handlers
from app.api.routes.profile import router
from app.application.exceptions import ProfileUnavailableError
from app.application.models.user_context import UserContext
from app.infrastructure.logger import bind_session_context
from tests.user_identity import TEST_USER_ID


@pytest.fixture
def client() -> Generator[TestClient]:
    app = FastAPI()
    register_exception_handlers(
        app, logger=MagicMock(), session_context_factory=bind_session_context
    )
    app.state.profile_service = AsyncMock()
    app.state.profile_service.save.side_effect = lambda profile: profile
    app.dependency_overrides[get_user_context] = lambda: UserContext(TEST_USER_ID)
    app.include_router(router, prefix="/api")

    with TestClient(app) as test_client:
        yield test_client


def test_save_profile_echoes_validated_contract_and_context_user(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/profile",
        json={
            "monthly_revenue": 4200,
            "objective": "Save for a trip in December",
            "risk_tolerance": "LOW",
            "preferences": "I do not want aggressive investments.",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "user_id": str(TEST_USER_ID),
        "monthly_revenue": "4200",
        "objective": "Save for a trip in December",
        "risk_tolerance": "LOW",
        "preferences": "I do not want aggressive investments.",
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("monthly_revenue", 0),
        ("objective", ""),
        ("risk_tolerance", "VERY_HIGH"),
        ("preferences", ""),
    ],
)
def test_save_profile_rejects_invalid_contract(
    client: TestClient, field: str, value: object
) -> None:
    payload = {
        "monthly_revenue": 4200,
        "objective": "Save for a trip",
        "risk_tolerance": "LOW",
        "preferences": "No aggressive investments.",
    }
    payload[field] = value

    assert client.post("/api/profile", json=payload).status_code == 422


@pytest.mark.parametrize("header", [None, "invalid", str(uuid4())])
def test_profile_rejects_missing_invalid_or_unknown_identity(
    client: TestClient, header: str | None
) -> None:
    del client.app.dependency_overrides[get_user_context]
    client.app.state.user_repository = AsyncMock()
    client.app.state.user_repository.exists.return_value = False
    response = client.post(
        "/api/profile",
        headers={"X-User-ID": header} if header else {},
        json={
            "monthly_revenue": 42,
            "objective": "Trip",
            "risk_tolerance": "LOW",
            "preferences": "Safe",
            "user_id": str(TEST_USER_ID),
        },
    )
    assert response.status_code == (404 if header and header != "invalid" else 422)
    client.app.state.profile_service.save.assert_not_awaited()


def test_profile_failure_is_public_and_not_reported_as_saved(
    client: TestClient,
) -> None:
    client.app.state.profile_service.save.side_effect = ProfileUnavailableError(
        "private URI"
    )
    response = client.post(
        "/api/profile",
        json={
            "monthly_revenue": 42,
            "objective": "Trip",
            "risk_tolerance": "LOW",
            "preferences": "Safe",
        },
    )
    assert response.status_code == 503
    assert "private URI" not in response.text
    assert response.json()["code"] == "profile_unavailable"
