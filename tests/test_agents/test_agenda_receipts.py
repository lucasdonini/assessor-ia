from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage

from app.infrastructure.agents.guardrails.output_guardrail import OutputGuardrailNode
from app.infrastructure.agents.tools.agenda import agenda_execution
from tests.test_services.test_event_service import creation


@pytest.mark.asyncio
async def test_model_cannot_rewrite_partial_failure_into_google_success():
    result = creation()
    result.google.state = "failed"
    generator = AsyncMock()
    guardrail = OutputGuardrailNode(
        text_generator=generator, logger_factory=lambda _: MagicMock()
    )
    with agenda_execution() as evidence:
        evidence.writes.append(result)
        output = await guardrail(
            {"messages": [AIMessage(content="Tudo criado no Google!")], "pii_map": {}}
        )
    response = output["messages"][0].content
    assert "registro local permanece" in response
    assert "Falha no Google" in response
    assert str(result.event.id) not in response
    assert str(result.operation_id) not in response
    assert result.proposal.title not in response
    generator.generate.assert_not_awaited()
