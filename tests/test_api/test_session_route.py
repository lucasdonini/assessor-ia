from collections.abc import Generator
from dataclasses import dataclass, field
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_chat_session_service, get_user_context
from app.api.middleware.exception_handler import register_exception_handlers
from app.api.routes.session import router
from app.application.models.user_context import UserContext
from app.application.ports.logger import Logger
from app.infrastructure.logger import bind_session_context
from app.infrastructure.session_coordinator import SessionCoordinator
from tests.user_identity import TEST_USER_ID

_SESSION_ID = "session-123"


@dataclass
class SessionServiceStub:
    summary: str | None = "Resumo da sessão"
    finalized_sessions: list[str] = field(default_factory=list)

    async def finalize_session(self, session_id: str, *, user_id) -> str | None:
        self.finalized_sessions.append(session_id)
        return self.summary


@pytest.fixture
def session_service() -> SessionServiceStub:
    return SessionServiceStub()


@pytest.fixture
def client(session_service: SessionServiceStub) -> Generator[TestClient]:
    app = FastAPI()
    app.state.session_coordinator = SessionCoordinator()
    app.dependency_overrides[get_user_context] = lambda: UserContext(TEST_USER_ID)
    app.state.session_context_factory = bind_session_context
    register_exception_handlers(
        app,
        logger=MagicMock(spec=Logger),
        session_context_factory=bind_session_context,
    )
    app.include_router(router, prefix="/api")

    def override_session_service() -> SessionServiceStub:
        return session_service

    app.dependency_overrides[get_chat_session_service] = override_session_service

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def test_finalize_session_returns_summary(
    client: TestClient, session_service: SessionServiceStub
) -> None:
    response = client.post(f"/api/session/{_SESSION_ID}/finalize")

    assert response.status_code == 200
    assert response.json() == {
        "session_id": _SESSION_ID,
        "session_summary": "Resumo da sessão",
    }
    assert session_service.finalized_sessions == [_SESSION_ID]


def test_finalize_session_accepts_missing_summary(
    client: TestClient, session_service: SessionServiceStub
) -> None:
    session_service.summary = None

    response = client.post(f"/api/session/{_SESSION_ID}/finalize")

    assert response.status_code == 200
    assert response.json() == {
        "session_id": _SESSION_ID,
        "session_summary": None,
    }
