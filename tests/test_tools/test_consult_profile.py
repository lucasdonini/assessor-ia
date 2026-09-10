import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.application.models.user_context import UserContext
from app.domain.model.user_profile import RiskTolerance, UserProfile
from app.infrastructure.agents._core.schemas.tool_response import (
    ToolFailure,
    ToolSuccess,
)
from app.infrastructure.agents._core.user_context import bind_user_context
from app.infrastructure.agents.tools.consult_profile import (
    ConsultProfileFoundResponse,
    ConsultProfileNotFoundResponse,
    ConsultProfileTool,
)
from app.services.user_profile_service import UserProfileService


@pytest.mark.asyncio
async def test_concurrent_tool_calls_use_server_identity() -> None:
    service = MagicMock(spec=UserProfileService)
    service.consult = AsyncMock(return_value=None)
    tool = ConsultProfileTool(service=service, logger_factory=lambda _: MagicMock())
    first, second = uuid4(), uuid4()

    async def consult(
        context: UserContext,
    ) -> ToolSuccess[ConsultProfileNotFoundResponse]:
        with bind_user_context(context):
            return await tool.ainvoke({"query": "crypto"})

    results = await asyncio.gather(
        consult(UserContext(first)), consult(UserContext(second))
    )
    assert all(isinstance(result, ToolSuccess) for result in results)
    assert all(
        isinstance(result.data, ConsultProfileNotFoundResponse) for result in results
    )
    assert all("tela Perfil" in result.data.detail for result in results)
    assert {c.kwargs["user_id"] for c in service.consult.await_args_list} == {
        first,
        second,
    }
    assert set(tool.tool_call_schema.model_json_schema()["properties"]) == {"query"}
    service.save.assert_not_called()


@pytest.mark.asyncio
async def test_profile_response_and_failure_do_not_expose_identity_or_errors() -> None:
    user_id = uuid4()
    service = MagicMock(spec=UserProfileService)
    service.consult = AsyncMock(
        return_value=UserProfile(
            user_id, Decimal("42.01"), "Trip", RiskTolerance.LOW, "No aggressive assets"
        )
    )
    tool = ConsultProfileTool(service=service, logger_factory=lambda _: MagicMock())
    with bind_user_context(UserContext(user_id)):
        result = await tool.ainvoke({"query": "crypto"})
        assert isinstance(result, ToolSuccess)
        assert isinstance(result.data, ConsultProfileFoundResponse)
        assert result.data.monthly_revenue == Decimal("42.01")
        assert result.data.preferences == "No aggressive assets"
        assert "user_id" not in result.data.model_dump()
        service.consult.side_effect = RuntimeError("private URI")
        result = await tool.ainvoke({"query": "crypto"})
    assert isinstance(result, ToolFailure)
    assert result.code == "unexpected_error"
    assert "private URI" not in result.error
