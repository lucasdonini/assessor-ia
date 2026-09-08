import logging

from beanie import init_beanie
from pymongo import AsyncMongoClient
from pymongo.monitoring import (
    CommandFailedEvent,
    CommandListener,
    CommandStartedEvent,
    CommandSucceededEvent,
    register,
)

from ..settings import PydanticSettings
from .entities.chat_session import ChatSessionDocument
from .entities.user_profile import UserProfileDocument

logger = logging.getLogger(__name__)


IGNORED_COMMANDS = {
    "ismaster",
    "ping",
    "hello",
    "buildinfo",
    "saslstart",
    "saslcontinue",
}


class LoggingMongoCommandListener(CommandListener):
    """
    Listener to log every query made to the
    mongo database to improve maintanability
    """

    def started(self, event: CommandStartedEvent) -> None:
        if event.command_name.lower() not in IGNORED_COMMANDS:
            logger.debug(
                "Mongo command started",
                extra={
                    "details": {
                        "command": event.command_name,
                        "database": event.database_name,
                        "query": str(event.command),
                    }
                },
            )

    def succeeded(self, event: CommandSucceededEvent) -> None:
        if event.command_name.lower() not in IGNORED_COMMANDS:
            logger.debug(
                "Mongo command succeeded",
                extra={
                    "details": {
                        "command": event.command_name,
                        "database": event.database_name,
                        "elapsed_ms": round(event.duration_micros / 1000, 2),
                    }
                },
            )

    def failed(self, event: CommandFailedEvent) -> None:
        if event.command_name.lower() not in IGNORED_COMMANDS:
            logger.debug(
                "Mongo command failed",
                extra={
                    "details": {
                        "command": event.command_name,
                        "database": event.database_name,
                        "error": str(event.failure),
                    }
                },
            )


class MongoManager:
    def __init__(self, settings: PydanticSettings) -> None:
        self._settings = settings
        self._client: AsyncMongoClient | None = None
        self._registered_listeners: bool = False

    async def init_database(self) -> None:
        """Initialize connection and map classes"""
        if self._client is None:
            self._client = AsyncMongoClient(
                self._settings.mongodb_uri.get_secret_value()
            )
        if not self._registered_listeners:
            register(LoggingMongoCommandListener())
        await init_beanie(
            database=self._client[self._settings.mongodb_dbname.get_secret_value()],
            document_models=[ChatSessionDocument, UserProfileDocument],
        )
        logger.debug("MongoDB initialized")
