import operator
from enum import StrEnum
from typing import Annotated, NotRequired

from langgraph.graph import MessagesState


class GraphState(MessagesState):
    called_agents: Annotated[list[str], operator.add]
    route: str
    pii_map: dict
    guardrail_reason: NotRequired[str | None]


class GraphStateKeys(StrEnum):
    MESSAGES = "messages"
    CALLED_AGENTS = "called_agents"
    ROUTE = "route"
    PII_MAP = "pii_map"
    GUARDRAIL_REASON = "guardrail_reason"
