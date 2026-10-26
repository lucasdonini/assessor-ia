from dishka import AsyncContainer, make_async_container

from .providers import (
    AgentGraphProvider,
    LoggingProvider,
    MongoProvider,
    PostgresProvider,
    QdrantProvider,
    ServicesProvider,
    SettingsProvider,
)
from .providers.google import GoogleProvider


def create_container() -> AsyncContainer:
    return make_async_container(
        SettingsProvider(),
        GoogleProvider(),
        LoggingProvider(),
        PostgresProvider(),
        MongoProvider(),
        QdrantProvider(),
        ServicesProvider(),
        AgentGraphProvider(),
    )
