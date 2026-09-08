from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from beanie import init_beanie
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pymongo import AsyncMongoClient
from qdrant_client import QdrantClient
from testcontainers.community.mongodb import MongoDbContainer

from app.api.routes.profile import router
from app.application.models.user_context import UserContext
from app.infrastructure.agents._core.user_context import bind_user_context
from app.infrastructure.agents.tools.consult_profile import ConsultProfileTool
from app.infrastructure.mongodb.entities.user_profile import UserProfileDocument
from app.infrastructure.mongodb.repositories.user_profile_repository import (
    BeanieUserProfileRepository,
)
from app.infrastructure.vectorstore.repositories.profile_preferences_index import (
    QDrantProfilePreferencesIndex,
)
from app.services.user_profile_service import UserProfileService

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_http_mongodb_qdrant_and_tool_workflow() -> None:
    # Disposable MongoDB; never connects to the application's configured database.
    with MongoDbContainer("mongo:7") as container:
        mongo = AsyncMongoClient(container.get_connection_url())
        qdrant = QdrantClient(":memory:")
        try:
            await init_beanie(
                database=mongo.profile_workflow_test,
                document_models=[UserProfileDocument],
            )
            embeddings = MagicMock()
            embeddings.generate.return_value = [1.0, 0.0]
            embeddings.generate_batch.return_value = [[1.0, 0.0]]
            index = QDrantProfilePreferencesIndex(
                client=qdrant, embeddings=embeddings, dimensions=2
            )
            await index.initialize()
            repository = BeanieUserProfileRepository()
            service = UserProfileService(
                repository=repository, index=index, logger=MagicMock()
            )
            first, second = uuid4(), uuid4()
            app = FastAPI()
            app.state.profile_service = service
            app.state.user_repository = AsyncMock()
            app.state.user_repository.exists.side_effect = lambda uid: (
                uid in {first, second}
            )
            app.include_router(router, prefix="/api")
            tool = ConsultProfileTool(
                service=service, logger_factory=lambda _: MagicMock()
            )
            with bind_user_context(UserContext(first)):
                assert "não cadastrado" in await tool.ainvoke(
                    {"query": "quanto guardar?"}
                )
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as http:
                payload = {
                    "monthly_revenue": 4200.01,
                    "objective": "Travel",
                    "risk_tolerance": "LOW",
                    "preferences": "Avoid aggressive assets",
                }
                assert (
                    await http.post("/api/profile", json=payload)
                ).status_code == 422
                for owner in (first, second):
                    response = await http.post(
                        "/api/profile", json=payload, headers={"X-User-ID": str(owner)}
                    )
                    assert response.status_code == 200
                    assert response.json()["user_id"] == str(owner)
                payload["preferences"] = "Liquidity for travel"
                response = await http.post(
                    "/api/profile", json=payload, headers={"X-User-ID": str(first)}
                )
                assert response.status_code == 200
                assert (await http.get("/api/profile")).status_code == 405
            stored = await repository.find_by_user_id(first)
            assert stored is not None and stored.monthly_revenue == Decimal("4200.01")
            assert await UserProfileDocument.count() == 2
            assert qdrant.count("profile_preferences").count == 2
            with bind_user_context(UserContext(first)):
                result = await tool.ainvoke({"query": "crypto"})
                assert "Liquidity for travel" in result
                assert "Avoid aggressive" not in result
            with bind_user_context(UserContext(second)):
                assert "Avoid aggressive" in await tool.ainvoke({"query": "crypto"})
        finally:
            await mongo.close()
            qdrant.close()
