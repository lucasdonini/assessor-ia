from contextlib import asynccontextmanager
from typing import AsyncGenerator, cast

from dishka import AsyncContainer
from fastapi import FastAPI

from .application.ports.agent_graph import AgentGraph
from .infrastructure.logger import setup_logger
from .infrastructure.settings import settings
from .infrastructure.vectorstore.ingestors.faq_ingestor import QDrantFaqIngestor


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logger()
    settings.validate_envs()

    container = cast(AsyncContainer, app.state.dishka_container)
    try:
        await container.get(AgentGraph)
        faq_ingestor = await container.get(QDrantFaqIngestor)
        faq_ingestor.ingest()
        yield
    finally:
        await container.close()
