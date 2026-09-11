import asyncio
import math
from datetime import datetime, timezone
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from qdrant_client import QdrantClient, models

from app.application.exceptions import SessionHistoryIndexError
from app.application.ports.logger import Logger, LoggerFactory
from app.domain.model.chat_session import ChatSessionSummarized
from app.infrastructure.vectorstore.config import SessionHistoryConfig


class HistoryEmbeddings(Protocol):
    def generate(self, text: str) -> list[float]: ...

    def generate_batch(self, batch: list[str]) -> list[list[float]]: ...


class _HistoryPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    user_id: UUID
    session_id: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    started_at: datetime


class QDrantSessionHistoryIndex:
    def __init__(
        self,
        *,
        client: QdrantClient,
        embeddings: HistoryEmbeddings,
        config: SessionHistoryConfig,
        logger_factory: LoggerFactory,
    ) -> None:
        if config.dimensions <= 0 or not -1 <= config.score_threshold <= 1:
            raise ValueError("Invalid history vector dimensions or score threshold")
        self._client = client
        self._embeddings = embeddings
        self._collection_name = config.collection_name
        self._dimensions = config.dimensions
        self._logger: Logger = logger_factory(__name__)
        self._score_threshold = config.score_threshold

    async def validate_collection(self) -> None:
        """Read existing metadata; never create or modify the collection."""
        try:
            info = await asyncio.to_thread(
                self._client.get_collection, self._collection_name
            )
            vectors = info.config.params.vectors
            vector = vectors.get("") if isinstance(vectors, dict) else vectors
            if (
                vector is None
                or vector.size != self._dimensions
                or vector.distance != models.Distance.COSINE
            ):
                raise ValueError(
                    "History requires the default Cosine vector with "
                    f"{self._dimensions} dimensions"
                )
            user_index = info.payload_schema.get("user_id")
            if (
                user_index is None
                or user_index.data_type != models.PayloadSchemaType.KEYWORD
            ):
                raise ValueError("History requires a keyword payload index on user_id")
        except Exception as error:
            self._logger.exception(
                "History collection validation failed", exception=error
            )
            raise SessionHistoryIndexError() from error

    def _validate_vector(self, vector: list[float]) -> None:
        if len(vector) != self._dimensions or not all(math.isfinite(v) for v in vector):
            raise ValueError("History embedding has invalid dimensions or values")

    async def index(self, session: ChatSessionSummarized) -> None:
        summary = (session.summary or "").strip()
        if not summary:
            return
        try:
            vectors = await asyncio.to_thread(
                self._embeddings.generate_batch, [summary]
            )
            if len(vectors) != 1:
                raise ValueError("Expected one history embedding")
            vector = vectors[0]
            self._validate_vector(vector)
            started_at = session.started_at
            # MongoDB can return naive UTC datetimes.
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)
            payload = _HistoryPayload(
                user_id=session.user_id,
                session_id=session.session_id,
                summary=summary,
                started_at=started_at,
            )
            point_id = uuid5(
                NAMESPACE_URL,
                f"assessoria:session-history:{session.user_id}:{session.session_id}",
            )
            await asyncio.to_thread(
                self._client.upsert,
                collection_name=self._collection_name,
                points=[
                    models.PointStruct(
                        id=str(point_id),
                        vector=vector,
                        payload=payload.model_dump(mode="json"),
                    )
                ],
                wait=True,
            )
        except Exception as error:
            self._logger.exception("History indexing failed", exception=error)
            raise SessionHistoryIndexError() from error

    async def search(
        self, search: str, *, user_id: UUID, limit: int
    ) -> list[ChatSessionSummarized]:
        search = search.strip()
        if not search:
            return []
        if limit <= 0:
            raise ValueError("History result limit must be positive")
        try:
            vector = await asyncio.to_thread(self._embeddings.generate, search)
            self._validate_vector(vector)
            response = await asyncio.to_thread(
                self._client.query_points,
                collection_name=self._collection_name,
                query=vector,
                query_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="user_id",
                            match=models.MatchValue(value=str(user_id)),
                        )
                    ]
                ),
                limit=limit,
                score_threshold=self._score_threshold,
                with_payload=["user_id", "session_id", "summary", "started_at"],
                with_vectors=False,
            )
            results: list[ChatSessionSummarized] = []
            for point in response.points:
                try:
                    payload = _HistoryPayload.model_validate(point.payload)
                except ValidationError:
                    self._logger.warning("Ignoring invalid history payload")
                    continue
                if payload.user_id != user_id or not payload.summary.strip():
                    self._logger.warning("Ignoring invalid history owner or summary")
                    continue
                results.append(
                    ChatSessionSummarized(
                        user_id=payload.user_id,
                        session_id=payload.session_id,
                        summary=payload.summary,
                        started_at=payload.started_at,
                    )
                )
            return results
        except Exception as error:
            self._logger.exception("History search failed", exception=error)
            raise SessionHistoryIndexError() from error
