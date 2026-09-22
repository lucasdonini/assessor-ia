from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from beanie import init_beanie
from pymongo import AsyncMongoClient
from testcontainers.community.mongodb import MongoDbContainer

from app.domain.exception.chat_session import ChatSessionNotFoundException
from app.domain.model.chat_entry import HumanMessage
from app.domain.model.chat_session import ChatSession
from app.infrastructure.mongodb.entities.chat_session import ChatSessionDocument
from app.infrastructure.mongodb.repositories.chat_session_repository import (
    BeanieChatSessionRepository,
)
from app.services.chat_session_service import ChatSessionService

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_mongodb_owner_filters_and_immutable_session_owner():
    with MongoDbContainer("mongo:7") as container:
        client = AsyncMongoClient(container.get_connection_url())
        try:
            await init_beanie(
                database=client.multiuser_test, document_models=[ChatSessionDocument]
            )
            repository = BeanieChatSessionRepository()
            first, second = uuid4(), uuid4()
            now = datetime.now(timezone.utc)
            for owner, session_id in [(first, "first"), (second, "second")]:
                await repository.get_or_create(
                    ChatSession(
                        user_id=owner,
                        session_id=session_id,
                        started_at=now,
                    )
                )
                await repository.append_entry(
                    session_id, HumanMessage(content="private"), now, user_id=owner
                )
                await repository.update_summary(
                    session_id, f"summary {owner}", now, user_id=owner
                )
            assert await repository.find_by_session_id("second", user_id=first) is None
            with pytest.raises(ChatSessionNotFoundException):
                await repository.get_or_create(
                    ChatSession(
                        user_id=first,
                        session_id="second",
                        started_at=now,
                    )
                )
            with pytest.raises(ChatSessionNotFoundException):
                await repository.append_entry(
                    "second", HumanMessage(content="intrusion"), now, user_id=first
                )
            await repository.update_summary("second", "intrusion", now, user_id=first)
            service = ChatSessionService(
                history_index=AsyncMock(),
                service=AsyncMock(),
                repository=repository,
                logger_factory=lambda _: MagicMock(),
                clock=MagicMock(now=lambda: now),
            )
            with pytest.raises(ChatSessionNotFoundException):
                await service.finalize_session("second", user_id=first)
            # Exercise the HTTP boundary with real session persistence and no LLM calls.
            from fastapi import FastAPI
            from httpx import ASGITransport, AsyncClient

            from app.api.dependencies import (
                bind_session_logging_context,
                coordinate_session,
                get_chat_session_service,
                get_graph,
                get_user_service,
            )
            from app.api.middleware.exception_handler import register_exception_handlers
            from app.api.routes.chat import router
            from app.infrastructure.logger import bind_session_context
            from app.services.user_service import UserService

            app = FastAPI()
            user_repository = AsyncMock()
            user_repository.exists.return_value = True
            graph = AsyncMock()
            app.dependency_overrides[get_graph] = lambda: graph
            app.dependency_overrides[get_chat_session_service] = lambda: service
            app.dependency_overrides[get_user_service] = lambda: UserService(
                user_repository
            )

            async def override_context_dependencies():
                yield

            app.dependency_overrides[bind_session_logging_context] = (
                override_context_dependencies
            )
            app.dependency_overrides[coordinate_session] = override_context_dependencies
            register_exception_handlers(
                app, logger=MagicMock(), session_context_factory=bind_session_context
            )
            app.include_router(router, prefix="/api")
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as http:
                response = await http.post(
                    "/api/chat/second",
                    headers={"X-User-ID": str(first)},
                    json={"message": "intrusion"},
                )
            assert response.status_code == 404
            graph.execute_agent_flux.assert_not_awaited()
            history = await repository.find_summaries(user_id=first)
            assert [item.session_id for item in history] == ["first"]
            protected = await repository.find_by_session_id("second", user_id=second)
            assert protected.summary == f"summary {second}"
            assert len(protected.entries) == 1
        finally:
            await client.close()
