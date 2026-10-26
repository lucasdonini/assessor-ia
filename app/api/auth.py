import secrets
from typing import Annotated

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import Depends, HTTPException, Request

from app.application.models.google_identity import WebSession
from app.services.auth_service import AuthenticationError, AuthService

COOKIE = "assessor_session"
OAUTH_COOKIE = "assessor_oauth"


@inject
def get_auth_service(service: FromDishka[AuthService]) -> AuthService:
    return service


async def authenticated_session(
    request: Request,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> WebSession:
    try:
        session = await service.session(request.cookies.get(COOKIE))
    except AuthenticationError:
        raise HTTPException(401, "Entre com sua conta Google.") from None
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        if not secrets.compare_digest(
            request.headers.get("X-CSRF-Token", ""), session.csrf
        ):
            raise HTTPException(403, "Atualize a página e tente novamente.")
    return session
