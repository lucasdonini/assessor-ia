import logging

from app.infrastructure.oauth_logging import OAuthAccessLogFilter


def test_access_log_removes_callback_codes_and_state():
    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        "",
        1,
        '%s - "%s %s HTTP/%s" %d',
        (
            "client",
            "GET",
            "/api/auth/google/callback?code=secret&state=private",
            "1.1",
            303,
        ),
        None,
    )
    assert OAuthAccessLogFilter().filter(record)
    assert "secret" not in record.getMessage()
    assert "private" not in record.getMessage()
    assert "/api/auth/google/callback" in record.getMessage()
