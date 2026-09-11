from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.ports.logger import Logger
from app.domain.model.chat_entry import (
    AssistantMessage,
    ChatError,
    HumanMessage,
)
from app.services.session_summary_service import SessionSummaryService


class TestSessionSummaryService:
    @pytest.fixture
    def service(self):
        text_generator = MagicMock()
        text_generator.generate = AsyncMock()
        logger = MagicMock(spec=Logger)
        return SessionSummaryService(text_generator, logger_factory=lambda _: logger)

    @pytest.mark.asyncio
    async def test_summarize_session(self, service):
        entries = (
            HumanMessage(content="Gastei 100 reais"),
            AssistantMessage(content="Registrado como despesa"),
        )
        service._text_generator.generate.return_value = (
            "Usuário registrou despesa de 100 reais."
        )

        result = await service.summarize_session(entries)

        assert result == "Usuário registrou despesa de 100 reais."
        service._text_generator.generate.assert_awaited_once()

    def test_format_conversation(self, service):
        entries = (
            HumanMessage(content="Olá"),
            ChatError(
                exception="ValueError",
                summary="Ocorreu um erro interno inesperado.",
            ),
            AssistantMessage(content="Oi!"),
        )
        expected = (
            "human: Olá\n"
            "ERROR: ValueError -> Ocorreu um erro interno inesperado.\n"
            "assistant: Oi!"
        )
        result = service._format_conversation(entries)
        assert result == expected

    @pytest.mark.asyncio
    async def test_summarize_session_empty(self, service):
        service._text_generator.generate.return_value = "Nenhuma conversa para resumir."

        result = await service.summarize_session(())

        assert result == "Nenhuma conversa para resumir."

    @pytest.mark.asyncio
    async def test_summarize_session_calls_text_generator(self, service):
        entries = (HumanMessage(content="teste"),)
        service._text_generator.generate.return_value = "resumo"

        await service.summarize_session(entries)

        service._text_generator.generate.assert_awaited_once()
        prompt_arg = service._text_generator.generate.call_args[0][0]
        assert "{conversa}" not in prompt_arg
        assert "teste" in prompt_arg

    @pytest.mark.asyncio
    async def test_summarize_exception(self, service):
        service._text_generator.generate.return_value = (
            "Ocorreu um erro interno inesperado."
        )

        try:
            raise ValueError("Algo deu errado")
        except ValueError as exc:
            result = await service.summarize_exception(exc)

        assert result == "Ocorreu um erro interno inesperado."
        service._text_generator.generate.assert_awaited_once()
