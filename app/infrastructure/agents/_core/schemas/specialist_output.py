from typing import Optional

from pydantic import BaseModel

from app.domain.model.event import EventCreation


class SpecialistOutput(BaseModel):
    dominio: str
    intencao: str
    resposta: str
    recomendacao: str = ""
    esclarecer: Optional[str] = None
    janela_tempo: Optional[dict] = None


class FinancialOutput(SpecialistOutput):
    dominio: str = "financeiro"
    escrita: Optional[list[dict]] = None
    indicadores: Optional[dict] = None


class AgendaOutput(SpecialistOutput):
    dominio: str = "agenda"
    acompanhamento: Optional[str] = None
    evento: Optional[dict] = None
    escrita: EventCreation | None = None
