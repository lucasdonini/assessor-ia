from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_user_context
from app.api.routes.profile import router
from app.application.models.user_context import UserContext
from tests.user_identity import TEST_USER_ID


@pytest.fixture
def client() -> Generator[TestClient]:
    app = FastAPI()
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
