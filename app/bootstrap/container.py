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


def create_container() -> AsyncContainer:
    return make_async_container(
        SettingsProvider(),
        LoggingProvider(),
        PostgresProvider(),
        MongoProvider(),
        QdrantProvider(),
        ServicesProvider(),
        AgentGraphProvider(),
    )
