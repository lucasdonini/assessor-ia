from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_DUMMY_API_KEY = "No API key provided"


class PydanticSettings(BaseSettings):
    gemini_api_key: SecretStr = SecretStr(_DUMMY_API_KEY)
    groq_api_key: SecretStr = SecretStr(_DUMMY_API_KEY)

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


settings = PydanticSettings()
