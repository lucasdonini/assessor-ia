from typing import Annotated
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.auth import get_auth_service
from app.api.dependencies import get_user_context
from app.application.models.google_identity import WebSession
from app.application.models.user_context import UserContext
from app.services.auth_service import AuthenticationError


def test_verified_session_overrides_forged_header_and_requires_csrf():
    app = FastAPI()
    service = AsyncMock()
    owner = uuid4()
    service.session.return_value = WebSession(
        user_id=owner, subject="subject", email="a@example.com", csrf="trusted"
    )
    app.dependency_overrides[get_auth_service] = lambda: service

    @app.api_route("/private", methods=["GET", "POST"])
    def private(context: Annotated[UserContext, Depends(get_user_context)]):
        return {"id": str(context.user_id)}

    with TestClient(app) as client:
        assert client.get("/private", headers={"X-User-ID": str(uuid4())}).json() == {
            "id": str(owner)
        }
        assert client.post("/private").status_code == 403
        assert (
            client.post("/private", headers={"X-CSRF-Token": "trusted"}).status_code
            == 200
        )
        service.session.side_effect = AuthenticationError()
        assert client.get("/private").status_code == 401
        assert (
            client.get("/private", headers={"X-User-ID": str(owner)}).status_code == 401
        )
