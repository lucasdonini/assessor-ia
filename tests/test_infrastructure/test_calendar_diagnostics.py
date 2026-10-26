import json

import pytest
from mcp.types import CallToolResult, TextContent

from app.infrastructure.agents.tools.agenda import creation_message
from app.infrastructure.google_calendar import tool_error_category
from tests.test_services.test_event_service import creation


@pytest.mark.parametrize(
    "text,category",
    [
        (
            "Access requires that your project is enrolled in the "
            "Google Workspace Developer Preview Program",
            "preview_required",
        ),
        ("Request had insufficient authentication scopes.", "insufficient_scope"),
        ('{"error":{"status":"PERMISSION_DENIED"}}', "permission_denied"),
        ("INVALID_ARGUMENT", "invalid_arguments"),
        ("Private event title for private@example.com", "unclassified"),
    ],
)
def test_diagnostic_is_a_fixed_label_not_provider_text(text, category):
    result = CallToolResult(
        content=[TextContent(type="text", text=text)], is_error=True
    )
    assert tool_error_category(result) == category


def test_structured_failure_is_classified_without_echoing_secrets():
    result = CallToolResult(
        content=[],
        structured_content={
            "error": {
                "reason": "ACCESS_TOKEN_SCOPE_INSUFFICIENT",
                "private": "Bearer private-token",
            }
        },
        is_error=True,
    )
    assert tool_error_category(result) == "insufficient_scope"


@pytest.mark.parametrize(
    "state", ["succeeded", "failed", "pending", "unknown", "not_connected"]
)
def test_creation_messages_never_expose_internal_ids(state):
    result = creation()
    result.google.state = state
    result.google.google_id = "private-google-id"
    message = creation_message(result)
    assert str(result.event.id) not in message
    assert str(result.operation_id) not in message
    assert "private-google-id" not in message


def test_preview_block_explains_partial_success_without_technical_ids():
    result = creation()
    result.google.state = "failed"
    result.google.error_category = "preview_required"
    message = creation_message(result)
    assert "registro local permanece" in message
    assert "acesso antecipado" in message
    assert str(result.event.id) not in message
    # Old receipts, written before error_category existed, remain readable.
    from app.domain.model.event import EventCreation

    raw = result.model_dump(mode="json")
    raw["google"].pop("error_category")
    assert (
        EventCreation.model_validate_json(json.dumps(raw)).google.error_category is None
    )
