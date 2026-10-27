from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DUMMY_API_KEY = "No API key provided"


class PydanticSettings(BaseSettings):
    monitor_operator_emails: tuple[str, ...] = ()
    langsmith_tracing: bool = False
    langsmith_api_key: SecretStr = SecretStr("")
    langsmith_project: str = "assessor-ia"

    @field_validator("monitor_operator_emails")
    @classmethod
    def validate_operator_emails(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(sorted({value.strip().casefold() for value in values}))
        for email in normalized:
            if (
                email.count("@") != 1
                or any(char.isspace() for char in email)
                or any(char in email for char in "*<>;,:")
                or not all(email.split("@"))
            ):
                raise ValueError(
                    "Configure operator emails as complete email addresses"
                )
        return normalized

    google_client_id: str = ""
    google_client_secret: SecretStr = SecretStr("")
    google_calendar_client_id: str = ""
    google_calendar_client_secret: SecretStr = SecretStr("")
    google_login_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"
    google_calendar_redirect_uri: str = (
        "http://localhost:8000/api/calendar/google/callback"
    )
    app_frontend_url: str = "http://localhost:8000/"
    auth_secure_cookies: bool = True
    google_token_encryption_key: SecretStr = SecretStr("")
    google_token_key_id: str = "v1"
    google_calendar_transport: Literal["rest", "mcp"] = "rest"
    google_calendar_mcp_url: str = "https://calendarmcp.googleapis.com/mcp/v1"
    gemini_api_key: SecretStr = SecretStr(_DUMMY_API_KEY)
    groq_api_key: SecretStr = SecretStr(_DUMMY_API_KEY)
    typesafe_api_key: SecretStr = SecretStr("")

    postgres_url: SecretStr = SecretStr("postgresql://localhost:5432/acessoriadb")

    mongodb_uri: SecretStr = SecretStr("mongodb://localhost:27017")
    mongodb_dbname: SecretStr = SecretStr("assessoria")

    log_level: Literal["INFO", "DEBUG"] = "INFO"
    log_to_file: bool = False
    log_file: str = "logs/app.log"
    app_timezone: str = "America/Sao_Paulo"
    agent_execution_timeout_seconds: float = Field(default=120.0, gt=0)
    llm_request_timeout_seconds: float = Field(default=30.0, gt=0)

    qdrant_api_key: SecretStr = SecretStr(_DUMMY_API_KEY)
    qdrant_url: SecretStr = SecretStr("")
    history_collection_name: str = "session-history"
    faq_collection_alias: str = "faq-current"
    faq_collection_prefix: str = "faq-chunks"
    embedding_dimmensions: int = Field(default=768, gt=0)

    faq_chunk_size: int = Field(default=700, gt=0)
    faq_chunk_overlap: int = Field(default=150, ge=0)
    faq_ingestion_batch_size: int = Field(default=50, gt=0)
    faq_search_score_threshold: float = Field(default=0.52, ge=0, le=1)
    ingest_faq_pdf: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="allow")

    def _validate_missing_keys(self) -> None:
        missing_keys = [
            key
            for key, value in (
                ("GEMINI_API_KEY", self.gemini_api_key),
                ("GROQ_API_KEY", self.groq_api_key),
                ("QDRANT_API_KEY", self.qdrant_api_key),
                ("QDRANT_URL", self.qdrant_url),
            )
            if value.get_secret_value() == _DUMMY_API_KEY
            or value.get_secret_value().strip() == ""
        ]
        if missing_keys:
            variables = ", ".join(missing_keys)
            raise ValueError(f"Configure missing envs: {variables}.")

    def _validate_chunk_overlap(self) -> None:
        if self.faq_chunk_overlap >= self.faq_chunk_size:
            raise ValueError(
                "Chunk overlap must be smaller than chunk size. "
                f"Overlap: {self.faq_chunk_overlap}, "
                f"Size: {self.faq_chunk_size}."
            )

    def validate_envs(self) -> None:
        self._validate_missing_keys()
        self._validate_chunk_overlap()
        if not self.auth_secure_cookies:
            from urllib.parse import urlparse

            urls = (
                self.app_frontend_url,
                self.google_login_redirect_uri,
                self.google_calendar_redirect_uri,
            )
            if any(
                urlparse(url).hostname not in {"localhost", "127.0.0.1"} for url in urls
            ):
                raise ValueError("Insecure cookies are restricted to localhost")


settings = PydanticSettings()
