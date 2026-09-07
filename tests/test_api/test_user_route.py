from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_user_context
from app.api.routes.user import router
from app.domain.model.user import User


def test_user_registry_and_required_identity():
    from typing import Annotated

    from fastapi import Depends

    from app.application.models.user_context import UserContext

    user = User(uuid4(), datetime.now(timezone.utc))
    app = FastAPI()
    repository = AsyncMock()
    repository.create.return_value = user
    repository.list_users.return_value = [user]
    repository.exists.side_effect = lambda user_id: user_id == user.id
    app.state.user_repository = repository
    app.include_router(router, prefix="/api")

    @app.get("/identity")
    def identity(context: Annotated[UserContext, Depends(get_user_context)]):
        return {"id": str(context.user_id)}

    with TestClient(app) as client:
        assert client.post("/api/users").json()["id"] == str(user.id)
        assert client.get("/api/users").json()[0]["id"] == str(user.id)
        assert client.get("/identity").status_code == 422
        assert client.get("/identity", headers={"X-User-ID": "bad"}).status_code == 422
        assert (
            client.get("/identity", headers={"X-User-ID": str(uuid4())}).status_code
            == 404
        )
        assert client.get("/identity", headers={"X-User-ID": str(user.id)}).json() == {
            "id": str(user.id)
        }
