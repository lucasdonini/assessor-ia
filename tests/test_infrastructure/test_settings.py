import pytest
from pydantic import ValidationError

from app.infrastructure.settings import PydanticSettings


def test_settings_use_expected_defaults() -> None:
    settings = PydanticSettings(_env_file=None)

    assert settings.log_level == "INFO"
    assert settings.log_to_file is False
    assert settings.log_file == "logs/app.log"
    assert settings.app_timezone == "America/Sao_Paulo"
    assert settings.agent_execution_timeout_seconds == 120.0
    assert settings.llm_request_timeout_seconds == 30.0
    assert settings.history_collection_name == "session-history"
    assert settings.faq_collection_alias == "faq-current"
    assert settings.faq_collection_prefix == "faq-chunks"
    assert settings.embedding_dimmensions == 768
    assert settings.faq_chunk_size == 700
    assert settings.faq_chunk_overlap == 150
    assert settings.faq_ingestion_batch_size == 50
    assert settings.ingest_faq_pdf is False


@pytest.mark.parametrize("level", ["INFO", "DEBUG"])
def test_settings_accept_valid_log_levels(level: str) -> None:
    settings = PydanticSettings(_env_file=None, log_level=level)

    assert settings.log_level == level


def test_settings_reject_invalid_log_level() -> None:
    with pytest.raises(ValidationError, match="log_level"):
        PydanticSettings(_env_file=None, log_level="WARNING")


@pytest.mark.parametrize(
    "field",
    ["agent_execution_timeout_seconds", "llm_request_timeout_seconds"],
)
def test_settings_reject_non_positive_timeouts(field: str) -> None:
    with pytest.raises(ValidationError, match=field):
        PydanticSettings(_env_file=None, **{field: 0})


def test_settings_reject_dummy_api_keys_at_boot() -> None:
    settings = PydanticSettings(_env_file=None)

    with pytest.raises(
        ValueError,
        match="GEMINI_API_KEY, GROQ_API_KEY, QDRANT_API_KEY, QDRANT_URL",
    ):
        settings.validate_envs()


def test_settings_accept_configured_api_keys() -> None:
    settings = PydanticSettings(
        _env_file=None,
        gemini_api_key="gemini-key",
        groq_api_key="groq-key",
        qdrant_api_key="qdrant-key",
        qdrant_url="https://qdrant.example.com",
    )

    settings.validate_envs()
