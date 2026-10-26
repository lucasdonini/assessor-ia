from typing import Annotated, Literal

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from app.api.auth import (
    COOKIE,
    OAUTH_COOKIE,
    authenticated_session,
    get_auth_service,
)
from app.application.models.google_identity import WebSession
from app.infrastructure.config import GoogleConfig
from app.services.auth_service import AuthService

router = APIRouter()


def set_cookie(
    response: Response, key: str, value: str, config: GoogleConfig, ttl: int
) -> None:
    response.set_cookie(
        key,
        value,
        max_age=ttl,
        httponly=True,
        secure=config.secure_cookies,
        samesite="lax",
        path="/",
    )


@router.get("/auth/me")
async def me(
    session: Annotated[WebSession, Depends(authenticated_session)],
) -> dict[str, str]:
    return {"id": str(session.user_id), "email": session.email, "csrf": session.csrf}


@router.get("/auth/google/start")
@inject
async def login_start(
    service: FromDishka[AuthService], config: FromDishka[GoogleConfig]
) -> Response:
    try:
        url, state = await service.begin("login")
    except ValueError:
        raise HTTPException(503, "Login Google ainda não configurado.") from None
    response = RedirectResponse(url, status_code=303)
    set_cookie(response, OAUTH_COOKIE, state, config, 600)
    return response


async def callback(
    purpose: Literal["login", "calendar"],
    request: Request,
    service: AuthService,
    config: GoogleConfig,
) -> Response:
    response = RedirectResponse(config.frontend_url, status_code=303)
    response.delete_cookie(OAUTH_COOKIE, path="/")
    try:
        token = await service.callback(
            purpose,
            request.query_params.get("code", ""),
            request.query_params.get("state", ""),
            request.cookies.get(OAUTH_COOKIE, ""),
            request.cookies.get(COOKIE),
        )
    except Exception:
        response.headers["location"] = config.frontend_url + "?auth_error=1"
        return response
    if token:
        set_cookie(response, COOKIE, token, config, 86400)
    return response


@router.get("/auth/google/callback")
@inject
async def login_callback(
    request: Request, service: FromDishka[AuthService], config: FromDishka[GoogleConfig]
) -> Response:
    return await callback("login", request, service, config)


@router.get("/calendar/google/callback")
@inject
async def calendar_callback(
    request: Request, service: FromDishka[AuthService], config: FromDishka[GoogleConfig]
) -> Response:
    return await callback("calendar", request, service, config)


@router.post("/auth/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    session: Annotated[WebSession, Depends(authenticated_session)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> None:
    await service.logout(request.cookies.get(COOKIE))
    response.delete_cookie(COOKIE, path="/")


@router.post("/calendar/google/connect")
@inject
async def calendar_connect(
    request: Request,
    session: Annotated[WebSession, Depends(authenticated_session)],
    service: FromDishka[AuthService],
    config: FromDishka[GoogleConfig],
) -> Response:
    url, state = await service.begin("calendar", request.cookies.get(COOKIE))
    from fastapi.responses import JSONResponse

    response = JSONResponse({"url": url})
    set_cookie(response, OAUTH_COOKIE, state, config, 600)
    return response


@router.get("/calendar/connection")
async def connection(
    session: Annotated[WebSession, Depends(authenticated_session)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> dict[str, object]:
    return (await service.connection(session.user_id)).model_dump()


@router.delete("/calendar/connection")
async def disconnect(
    session: Annotated[WebSession, Depends(authenticated_session)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> dict[str, bool]:
    revoked = await service.disconnect(session.user_id)
    return {"connected": False, "revoked": revoked}
