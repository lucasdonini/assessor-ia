from dishka import Provider, Scope, provide

from app.infrastructure.config import (
    AgentRuntimeConfig,
    MongoConfig,
    PostgresConfig,
    ProfileIndexConfig,
)
from app.infrastructure.settings import PydanticSettings, settings
from app.infrastructure.vectorstore.config import SessionHistoryConfig


class SettingsProvider(Provider):
    scope = Scope.APP

    @provide
    def settings(self) -> PydanticSettings:
        return settings

    @provide
    def history_config(self, config: PydanticSettings) -> SessionHistoryConfig:
        return SessionHistoryConfig(
            collection_name=config.history_collection_name,
            dimensions=config.embedding_dimmensions,
        )

    @provide
    def mongo_config(self, config: PydanticSettings) -> MongoConfig:
        return MongoConfig(
            uri=config.mongodb_uri.get_secret_value(),
            database_name=config.mongodb_dbname.get_secret_value(),
        )

    @provide
    def postgres_config(self, config: PydanticSettings) -> PostgresConfig:
        return PostgresConfig(url=config.postgres_url.get_secret_value())

    @provide
    def agent_runtime_config(self, config: PydanticSettings) -> AgentRuntimeConfig:
        return AgentRuntimeConfig(
            timezone_name=config.app_timezone,
            execution_timeout_seconds=config.agent_execution_timeout_seconds,
        )

    @provide
    def profile_index_config(self, config: PydanticSettings) -> ProfileIndexConfig:
        return ProfileIndexConfig(dimensions=config.embedding_dimmensions)
