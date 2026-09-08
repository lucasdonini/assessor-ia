"""Explicit streaming backfill of saved summaries; never runs at startup."""

import argparse
import asyncio
from collections.abc import AsyncIterable

from pymongo import AsyncMongoClient

from app.application.ports.logger import Logger
from app.application.ports.session_history_index import SessionHistoryIndex
from app.domain.model.chat_session import ChatSessionSummarized
from app.infrastructure.mongodb.entities.chat_session import (
    ChatSessionDocument,
    ChatSessionSummaryProjection,
)
from app.infrastructure.mongodb.mappers.chat_session_mapper import (
    ChatSessionSummarizedMapper,
)


class HistoryIngestor:
    def __init__(self, *, history_index: SessionHistoryIndex, logger: Logger) -> None:
        self._history_index = history_index
        self._logger = logger

    async def ingest(self, sessions: AsyncIterable[ChatSessionSummarized]) -> int:
        count = 0
        async for session in sessions:
            if not (session.summary or "").strip():
                continue
            # Stop on failure: rerunning safely replaces already indexed points.
            await self._history_index.index(session)
            count += 1
        self._logger.info("History backfill completed", details={"indexed": count})
        return count


async def _run(*, check_only: bool, batch_size: int) -> None:
    from app.infrastructure.logger import create_logger, setup_logger
    from app.infrastructure.settings import settings
    from app.infrastructure.vectorstore.client import qdrant_client
    from app.infrastructure.vectorstore.embeddings import qdrant_embeddings
    from app.infrastructure.vectorstore.repositories.session_history_index import (
        QDrantSessionHistoryIndex,
    )

    setup_logger()
    logger = create_logger(__name__)
    index = QDrantSessionHistoryIndex(
        client=qdrant_client,
        embeddings=qdrant_embeddings,
        collection_name=settings.history_collection_name,
        dimensions=settings.embedding_dimmensions,
        logger=logger,
    )
    client: AsyncMongoClient = AsyncMongoClient(
        settings.mongodb_uri.get_secret_value(),
        uuidRepresentation="standard",
        tz_aware=True,
        serverSelectionTimeoutMS=10000,
    )
    try:
        await index.validate_collection()
        collection = client[settings.mongodb_dbname.get_secret_value()][
            ChatSessionDocument.Settings.name
        ]
        query = {"summary": {"$type": "string", "$regex": r"\S"}}
        if check_only:
            count = await collection.count_documents(query)
            print(f"Resumos disponíveis para indexação: {count}")
            return

        async def summaries() -> AsyncIterable[ChatSessionSummarized]:
            cursor = (
                collection.find(
                    query,
                    projection={
                        "_id": 0,
                        "user_id": 1,
                        "session_id": 1,
                        "summary": 1,
                        "started_at": 1,
                    },
                )
                .sort("_id", 1)
                .batch_size(batch_size)
            )
            async with cursor:
                async for document in cursor:
                    projection = ChatSessionSummaryProjection.model_validate(document)
                    yield ChatSessionSummarizedMapper.document_to_model(projection)

        count = await HistoryIngestor(history_index=index, logger=logger).ingest(
            summaries()
        )
        print(f"Resumos indexados: {count}")
    finally:
        await client.close()
        await asyncio.to_thread(qdrant_client.close)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Only validate and count")
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()
    if args.batch_size <= 0:
        parser.error("--batch-size must be positive")
    try:
        asyncio.run(_run(check_only=args.check, batch_size=args.batch_size))
    except Exception:
        parser.exit(
            1, "Não foi possível concluir a carga do histórico. Consulte os logs.\n"
        )


if __name__ == "__main__":
    main()
