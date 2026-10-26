from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Annotated, Literal
from uuid import UUID, uuid4, uuid5

from pydantic import BaseModel, Field

from app.application.models.event_query import EventQuery
from app.domain.model.event import Event, EventCreation, EventDraft
from app.infrastructure.agents._core.contracts.agent_tool import AgentTool
from app.infrastructure.agents._core.user_context import get_user_context
from app.services.event_service import EventService


@dataclass
class AgendaEvidence:
    execution_id: UUID = field(default_factory=uuid4)
    writes: list[EventCreation] = field(default_factory=list)


_evidence: ContextVar[AgendaEvidence] = ContextVar("agenda_evidence")


@contextmanager
def agenda_execution() -> Iterator[AgendaEvidence]:
    evidence = AgendaEvidence()
    token = _evidence.set(evidence)
    try:
        yield evidence
    finally:
        _evidence.reset(token)


def agenda_evidence() -> AgendaEvidence:
    return _evidence.get(AgendaEvidence())


class AddEventArgs(BaseModel):
    event: EventDraft


class AddEventTool(AgentTool[AddEventArgs, EventCreation]):
    redact_payloads: bool = True
    name: Literal["add_event"] = "add_event"
    args_schema: type[AddEventArgs] = AddEventArgs
    description: str = (
        "Cria um compromisso local e tenta copiá-lo para o Google conectado. "
        "Exige título, início e fim com fuso. Conflitos geram proposta sem gravar; "
        "o usuário confirma pelo botão na interface. Não aceita confirmação do modelo."
    )
    service: Annotated[EventService, Field(exclude=True)]

    async def _execute(self, args: AddEventArgs) -> EventCreation:
        evidence = _evidence.get()
        operation = uuid5(evidence.execution_id, args.event.model_dump_json())
        result = await self.service.create(
            get_user_context().user_id, operation, args.event
        )
        evidence.writes.append(result)
        return result


class QueryEventsArgs(BaseModel):
    query: EventQuery = Field(default_factory=EventQuery)


class QueryEventsResponse(BaseModel):
    events: list[Event]
    scope: str = (
        "Somente compromissos locais do Assessor; "
        "não inclui eventos exclusivos do Google."
    )
    potentially_truncated: bool


class QueryEventsTool(AgentTool[QueryEventsArgs, QueryEventsResponse]):
    redact_payloads: bool = True
    name: Literal["query_events"] = "query_events"
    args_schema: type[QueryEventsArgs] = QueryEventsArgs
    description: str = (
        "Consulta compromissos locais por texto/data em America/Sao_Paulo; "
        "não consulta Google nem histórico de conversas."
    )
    service: Annotated[EventService, Field(exclude=True)]

    async def _execute(self, args: QueryEventsArgs) -> QueryEventsResponse:
        events = await self.service.query(get_user_context().user_id, args.query)
        return QueryEventsResponse(
            events=events, potentially_truncated=len(events) == args.query.limit
        )


def creation_message(result: EventCreation) -> str:
    if result.requires_confirmation:
        return (
            "Há conflito com compromissos locais. Nada foi registrado. "
            "Revise os horários e use Confirmar conflito na interface "
            "se quiser continuar."
        )
    if result.event is None:
        return "Não foi possível comprovar o registro do compromisso."
    suffix = {
        "succeeded": "Também criado no Google Calendar.",
        "failed": "Falha no Google Calendar. O registro local permanece.",
        "not_connected": "Google Calendar não conectado; registro somente local.",
        "pending": "Resultado no Google ainda não confirmado. Não repita o registro.",
        "unknown": "Resultado no Google incerto; verifique antes de repetir.",
    }[result.google.state]
    if (
        result.google.state == "failed"
        and result.google.error_category == "preview_required"
    ):
        suffix = (
            "O registro local permanece. A conexão MCP com o Google depende "
            "da liberação do aplicativo no programa de acesso antecipado."
        )
    return f"Compromisso registrado no Assessor. {suffix}"
