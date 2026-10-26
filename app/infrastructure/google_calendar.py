import asyncio
import json
import logging
from typing import Any
from uuid import UUID

import httpx
import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult

from app.domain.model.event import CalendarErrorCategory, CalendarReceipt, EventDraft
from app.infrastructure.config import GoogleConfig
from app.services.auth_service import AuthenticationError, AuthService


def http_errors(
    error: BaseException,
) -> list[httpx.HTTPStatusError | httpx2.HTTPStatusError]:
    if isinstance(error, BaseExceptionGroup):
        return [child for item in error.exceptions for child in http_errors(item)]
    if isinstance(error, (httpx.HTTPStatusError, httpx2.HTTPStatusError)):
        return [error]
    return []


def service_disabled(error: BaseException) -> bool:
    for item in http_errors(error):
        if item.response.status_code != 403:
            continue
        try:
            details = item.response.json().get("error", {}).get("details", [])
        except ValueError, AttributeError:
            continue
        if any(
            isinstance(detail, dict)
            and detail.get("reason") == "SERVICE_DISABLED"
            and detail.get("domain") == "googleapis.com"
            and detail.get("metadata", {}).get("service")
            == "calendarmcp.googleapis.com"
            for detail in details
        ):
            return True
    return False


class GoogleCalendarGateway:
    def __init__(self, auth: AuthService, config: GoogleConfig) -> None:
        self._auth = auth
        self._config = config

    async def create(self, user_id: UUID, event: EventDraft) -> CalendarReceipt:
        try:
            async with self._auth.calendar_access(user_id) as token:
                if token is None:
                    return CalendarReceipt(state="not_connected")
                return await self._create(token, event)
        except AuthenticationError, httpx.HTTPStatusError, ValueError:
            return CalendarReceipt(state="failed", code="reconnect_required")

    async def _create(self, token: str, event: EventDraft) -> CalendarReceipt:
        headers = {"Authorization": "Bearer " + token}
        submitted = False
        known_receipt: CalendarReceipt | None = None
        rejection: httpx2.HTTPStatusError | None = None

        async def capture_rejection(response: httpx2.Response) -> None:
            nonlocal rejection
            if response.status_code >= 400:
                await response.aread()
                rejection = httpx2.HTTPStatusError(
                    "Provider rejected request",
                    request=response.request,
                    response=response,
                )

        try:
            async with httpx2.AsyncClient(
                headers=headers,
                timeout=15,
                event_hooks={"response": [capture_rejection]},
            ) as client:
                async with streamable_http_client(
                    self._config.mcp_url, http_client=client
                ) as streams:
                    async with ClientSession(*streams) as session:
                        await session.initialize()
                        catalog = await session.list_tools()
                        tool = next(
                            (t for t in catalog.tools if t.name == "create_event"), None
                        )
                        if tool is None:
                            return CalendarReceipt(
                                state="failed", code="unsupported_catalog"
                            )
                        properties = tool.input_schema.get("properties", {})
                        if not {"summary", "startTime", "endTime"}.issubset(properties):
                            return CalendarReceipt(
                                state="failed", code="unsupported_schema"
                            )
                        payload: dict[str, Any] = {
                            "summary": event.title,
                            "startTime": event.start_time.isoformat(),
                            "endTime": event.end_time.isoformat(),
                            "timeZone": "America/Sao_Paulo",
                            "calendarId": "primary",
                        }
                        if event.location:
                            payload["location"] = event.location
                        if event.notes:
                            payload["description"] = event.notes
                        submitted = True
                        result = await session.call_tool("create_event", payload)
                        if result.is_error:
                            category = tool_error_category(result)
                            logging.getLogger(__name__).warning(
                                "Calendar MCP tool rejected event",
                                extra={
                                    "details": {
                                        "code": "mcp_tool_error",
                                        "category": category,
                                        "transport": "mcp",
                                    }
                                },
                            )
                            known_receipt = CalendarReceipt(
                                state="failed",
                                code="mcp_tool_error",
                                transport="mcp",
                                error_category=category,
                            )
                            return known_receipt
                        data = result.structured_content
                        if data is None:
                            for content in result.content:
                                if content.type == "text":
                                    parsed = json.loads(content.text)
                                    if isinstance(parsed, dict):
                                        data = parsed
                                        break
                        known_receipt = self._receipt(data, "mcp")
                        return known_receipt
        except asyncio.CancelledError:
            raise
        except Exception as error:
            if known_receipt is not None:
                return known_receipt
            if service_disabled(rejection or error):
                return await self._rest(headers, event)
            rejected = any(
                e.response.status_code in {400, 401, 403, 404, 429}
                for e in http_errors(rejection or error)
            )
            return CalendarReceipt(
                state="failed" if rejected or not submitted else "unknown",
                code="provider_rejected" if rejected else "mcp_unavailable",
                transport="mcp",
            )

    def _receipt(self, data: Any, transport: str) -> CalendarReceipt:
        if (
            not isinstance(data, dict)
            or not isinstance(data.get("id"), str)
            or not data["id"]
        ):
            return CalendarReceipt(state="unknown", code="missing_provider_id")
        link = data.get("htmlLink")
        # Only display links from the documented Google Calendar origin.
        from urllib.parse import urlparse

        safe_link = (
            link
            if isinstance(link, str)
            and urlparse(link).scheme == "https"
            and urlparse(link).hostname == "www.google.com"
            else None
        )
        return CalendarReceipt(
            state="succeeded",
            google_id=data["id"],
            link=safe_link,
            transport="mcp" if transport == "mcp" else "rest",
        )

    async def _rest(
        self, headers: dict[str, str], event: EventDraft
    ) -> CalendarReceipt:
        try:
            async with httpx.AsyncClient(headers=headers, timeout=15) as client:
                response = await client.post(
                    self._config.rest_url + "/calendars/primary/events",
                    json={
                        "summary": event.title,
                        "start": {
                            "dateTime": event.start_time.isoformat(),
                            "timeZone": "America/Sao_Paulo",
                        },
                        "end": {
                            "dateTime": event.end_time.isoformat(),
                            "timeZone": "America/Sao_Paulo",
                        },
                        "location": event.location or "",
                        "description": event.notes or "",
                    },
                )
                if response.status_code >= 400:
                    return CalendarReceipt(
                        state="failed" if response.status_code < 500 else "unknown",
                        code="rest_rejected",
                        transport="rest",
                    )
                return self._receipt(response.json(), "rest")
        except asyncio.CancelledError:
            raise
        except Exception:
            return CalendarReceipt(
                state="unknown", code="rest_unavailable", transport="rest"
            )


def tool_error_category(result: CallToolResult) -> CalendarErrorCategory:
    """Return only a fixed diagnostic label; never store/log provider text.

    MCP tool failures can carry details as structured data or text even when HTTP
    succeeds. Classification does not authorize a fallback or another create.
    """
    parts = [json.dumps(result.structured_content or {}, ensure_ascii=True)]
    parts.extend(block.text for block in result.content if block.type == "text")
    text = " ".join(parts).casefold()
    rules: tuple[tuple[CalendarErrorCategory, tuple[str, ...]], ...] = (
        (
            "preview_required",
            (
                "enrolled in the google workspace developer preview program",
                "requires enrollment in the google workspace developer preview",
            ),
        ),
        (
            "insufficient_scope",
            (
                "access_token_scope_insufficient",
                "insufficient authentication scopes",
                "insufficientpermissions",
                "insufficient_scope",
            ),
        ),
        (
            "unauthenticated",
            ("unauthenticated", "invalid credentials", "invalid_token"),
        ),
        ("service_disabled", ("service_disabled",)),
        (
            "permission_denied",
            ("permission_denied", "permission denied", "access_denied"),
        ),
        (
            "invalid_arguments",
            ("invalid_argument", "invalid argument", "invalidparams"),
        ),
        ("rate_limited", ("resource_exhausted", "ratelimitexceeded", "rate limit")),
        ("unavailable", ("unavailable", "internal server error")),
    )
    for category, markers in rules:
        if any(marker in text for marker in markers):
            return category
    return "unclassified"
