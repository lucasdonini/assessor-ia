from dishka import Provider, Scope, provide
from qdrant_client import QdrantClient

from app.application.ports.faq_search import FaqSearch
from app.application.ports.logger import LoggerFactory
from app.application.ports.profile_preferences_index import ProfilePreferencesIndex
from app.application.ports.session_history_index import SessionHistoryIndex
from app.infrastructure.config import ProfileIndexConfig
from app.infrastructure.vectorstore.client import qdrant_client
from app.infrastructure.vectorstore.config import SessionHistoryConfig
from app.infrastructure.vectorstore.embeddings import qdrant_embeddings
from app.infrastructure.vectorstore.ingestors.faq_ingestor import QDrantFaqIngestor
from app.infrastructure.vectorstore.repositories.faq_embedding_repository import (
    QDrantFaqSearch,
)
from app.infrastructure.vectorstore.repositories.profile_preferences_index import (
    QDrantProfilePreferencesIndex,
)
from app.infrastructure.vectorstore.repositories.session_history_index import (
    HistoryEmbeddings,
    QDrantSessionHistoryIndex,
)


async def build_history_index(
    client: QdrantClient,
    embeddings: HistoryEmbeddings,
    config: SessionHistoryConfig,
    logger_factory: LoggerFactory,
) -> SessionHistoryIndex:
    index = QDrantSessionHistoryIndex(
        client=client,
        embeddings=embeddings,
        config=config,
        logger_factory=logger_factory,
    )
    await index.validate_collection()
    return index


class QdrantProvider(Provider):
    scope = Scope.APP

    @provide
    def qdrant_client(self) -> QdrantClient:
        return qdrant_client

    @provide
    def history_embeddings(self) -> HistoryEmbeddings:
        return qdrant_embeddings

    history_index = provide(
        staticmethod(build_history_index), provides=SessionHistoryIndex
    )

    @provide
    async def profile_index(
        self,
        client: QdrantClient,
        embeddings: HistoryEmbeddings,
        config: ProfileIndexConfig,
    ) -> ProfilePreferencesIndex:
        index = QDrantProfilePreferencesIndex(
            client=client,
            embeddings=embeddings,
            dimensions=config.dimensions,
        )
        await index.initialize()
        return index

    @provide
    def faq_ingestor(self, logger_factory: LoggerFactory) -> QDrantFaqIngestor:
        return QDrantFaqIngestor(logger_factory=logger_factory)

    @provide
    def faq_search(self, logger_factory: LoggerFactory) -> FaqSearch:
        return QDrantFaqSearch(logger_factory=logger_factory)
