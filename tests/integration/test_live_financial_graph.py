"""Opt-in full graph evaluation with real models and fictional, non-writing stores.

Run as a module to avoid pytest's compatibility patches and exercise the same
LangChain/LangGraph construction as the application process.
"""

import asyncio
import json
import os
from contextlib import nullcontext
from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import pytest
from langchain_core.messages import AIMessage

from app.application.models.user_context import UserContext
from app.application.ports.faq_search import FaqSearch
from app.application.repositories.transaction_repository import TransactionRepository
from app.domain.model.chat_entry import HumanMessage
from app.domain.model.transaction import Transaction
from app.infrastructure.agents import build_agent_graph
from app.infrastructure.clock import SystemClock
from app.infrastructure.evidence_validator import JevEvidenceValidator
from app.infrastructure.llms import fast_llm
from app.infrastructure.settings import settings
from app.infrastructure.text_generator import LLMTextGenerator
from app.services.chat_history_service import ChatHistoryService
from app.services.transaction_service import TransactionService
from app.services.user_profile_service import UserProfileService

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def run_live_graph() -> dict[str, object]:
    records: list[Transaction] = []
    repository = AsyncMock(spec=TransactionRepository)

    async def save(transaction: Transaction, *, user_id: object) -> Transaction:
        saved = replace(transaction, id=uuid4())
        records.append(saved)
        return saved

    repository.add_transaction.side_effect = save
    repository.find.side_effect = lambda *args, **kwargs: list(records)
    repository.get_balance.return_value = 0
    repository.resolve_transaction.return_value = None
    history = AsyncMock(spec=ChatHistoryService)
    history.fetch_history.return_value = []
    profile = AsyncMock(spec=UserProfileService)
    profile.consult.return_value = None
    faq = MagicMock(spec=FaqSearch)
    faq.search.return_value = []

    def logger(_: str) -> MagicMock:
        return MagicMock()

    summaries = []
    async with httpx.AsyncClient() as client:
        validator = JevEvidenceValidator(
            client, settings.typesafe_api_key.get_secret_value(), logger
        )
        graph = build_agent_graph(
            transaction_service=TransactionService(repository, logger, validator),
            profile_service=profile,
            chat_history_service=history,
            faq_search=faq,
            text_generator=LLMTextGenerator(fast_llm),
            logger_factory=logger,
            trace_context_factory=lambda _: nullcontext(),
            interaction_incrementer=lambda: 1,
            clock=SystemClock("America/Sao_Paulo"),
            validator=validator,
            execution_timeout_seconds=90,
        )
        for question, amount in [
            ("Comprei um livro na Papelaria Aurora por 42 reais", 42),
            ("Paguei 25 reais de almoço na Cantina Horizonte", 25),
            ("Comprei uma camisa na Loja Boreal por 75 reais", 75),
        ]:
            before = len(records)
            session = str(uuid4())
            context = UserContext(uuid4())
            first = await graph.execute_agent_flux(
                HumanMessage(content=question), session, context=context
            )
            summaries.append(
                {"called_agents": first.called_agents, "content": first.message.content}
            )
            print(
                json.dumps({"fictional_turn": summaries[-1]}, ensure_ascii=True),
                flush=True,
            )
            assert "financial" in first.called_agents, summaries
            if len(records) == before:
                snapshot = await graph._agent_flux.aget_state(
                    {"configurable": {"thread_id": f"{context.user_id}:{session}"}}
                )
                print(
                    json.dumps(
                        {
                            "fictional_debug": [
                                msg.text
                                for msg in snapshot.values.get("messages", [])
                                if isinstance(msg, AIMessage)
                            ]
                        },
                        ensure_ascii=True,
                    )
                )
                confirmation = await graph.execute_agent_flux(
                    HumanMessage(content="Sim"), session, context=context
                )
                summaries.append(
                    {
                        "called_agents": confirmation.called_agents,
                        "content": confirmation.message.content,
                    }
                )
                assert "financial" in confirmation.called_agents, summaries
            assert len(records) == before + 1, summaries
            assert records[-1].amount == amount
            assert records[-1].source_text == question
    return {
        "synthetic_only": True,
        "real_models": True,
        "real_database_writes": 0,
        "simulated_writes": len(records),
        "turns": summaries,
    }


async def test_live_financial_graph():
    if os.environ.get("RUN_GRAPH_EVALUATION") != "1":
        pytest.skip("Opt in with RUN_GRAPH_EVALUATION=1; uses real model APIs")
    print(json.dumps(await run_live_graph(), ensure_ascii=True))


if __name__ == "__main__":
    if os.environ.get("RUN_GRAPH_EVALUATION") != "1":
        raise SystemExit("Set RUN_GRAPH_EVALUATION=1 to use real model APIs")
    print(json.dumps(asyncio.run(run_live_graph()), ensure_ascii=True))
