from unittest.mock import AsyncMock
from uuid import UUID

from app.application.models.google_identity import WebSession
from app.services.auth_service import AuthenticationError


def synthetic_auth_service(*owners: UUID) -> AsyncMock:
    """Replace only the external login/session store in HTTP persistence tests."""
    sessions = {
        str(owner): WebSession(
            user_id=owner,
            subject=str(owner),
            email="synthetic@example.com",
            csrf="test-csrf",
        )
        for owner in owners
    }

    async def resolve(token: str | None) -> WebSession:
        if token not in sessions:
            raise AuthenticationError()
        return sessions[token]

    service = AsyncMock()
    service.session.side_effect = resolve
    return service


TEST_USER_ID = UUID("123e4567-e89b-12d3-a456-426614174099")
