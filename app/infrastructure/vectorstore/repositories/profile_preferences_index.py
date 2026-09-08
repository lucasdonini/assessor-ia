import asyncio
import math
from typing import Protocol
from uuid import UUID

from qdrant_client import QdrantClient, models


class ProfileEmbeddings(Protocol):
    def generate(self, text: str) -> list[float]: ...

    def generate_batch(self, batch: list[str]) -> list[list[float]]: ...


class QDrantProfilePreferencesIndex:
    def __init__(
        self,
        *,
        client: QdrantClient,
        embeddings: ProfileEmbeddings,
        dimensions: int,
        collection_name: str = "profile_preferences",
    ) -> None:
        self._client = client
        self._embeddings = embeddings
        self._dimensions = dimensions
        self._collection_name = collection_name

    async def initialize(self) -> None:
        if not await asyncio.to_thread(
            self._client.collection_exists, self._collection_name
        ):
            await asyncio.to_thread(
                self._client.create_collection,
                collection_name=self._collection_name,
                vectors_config=models.VectorParams(
                    size=self._dimensions, distance=models.Distance.COSINE
                ),
            )
        info = await asyncio.to_thread(
            self._client.get_collection, self._collection_name
        )
        vectors = info.config.params.vectors
        if (
            not isinstance(vectors, models.VectorParams)
            or vectors.size != self._dimensions
            or vectors.distance != models.Distance.COSINE
        ):
            raise ValueError("Incompatible profile preferences collection")
        await asyncio.to_thread(
            self._client.create_payload_index,
            collection_name=self._collection_name,
            field_name="user_id",
            field_schema=models.PayloadSchemaType.KEYWORD,
            wait=True,
        )

    def _validate_vector(self, vector: list[float]) -> None:
        if len(vector) != self._dimensions or not all(math.isfinite(v) for v in vector):
            raise ValueError("Invalid profile embedding")

    async def upsert(self, preferences: str, *, user_id: UUID) -> None:
        vectors = await asyncio.to_thread(
            self._embeddings.generate_batch, [preferences]
        )
        if len(vectors) != 1:
            raise ValueError("Expected one profile embedding")
        self._validate_vector(vectors[0])
        await asyncio.to_thread(
            self._client.upsert,
            collection_name=self._collection_name,
            points=[
                models.PointStruct(
                    id=str(user_id),
                    vector=vectors[0],
                    payload={"user_id": str(user_id), "preferences": preferences},
                )
            ],
            wait=True,
        )

    async def search(self, query: str, *, user_id: UUID) -> list[str]:
        vector = await asyncio.to_thread(self._embeddings.generate, query)
        self._validate_vector(vector)
        response = await asyncio.to_thread(
            self._client.query_points,
            collection_name=self._collection_name,
            query=vector,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="user_id", match=models.MatchValue(value=str(user_id))
                    )
                ]
            ),
            limit=1,
            with_payload=True,
            with_vectors=False,
        )
        result: list[str] = []
        for point in response.points:
            payload = point.payload or {}
            preferences = payload.get("preferences")
            if payload.get("user_id") != str(user_id):
                raise ValueError("Unexpected profile owner")
            if not isinstance(preferences, str) or not preferences.strip():
                raise ValueError("Invalid profile preferences payload")
            result.append(preferences)
        return result
