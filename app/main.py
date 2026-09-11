from dishka import AsyncContainer
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api.middleware.exception_handler import register_exception_handlers
from .api.routes import ROUTES
from .bootstrap import create_container
from .infrastructure.logger import bind_session_context, create_logger
from .infrastructure.paths import FRONTEND
from .lifespan import lifespan


def create_app(container: AsyncContainer | None = None) -> FastAPI:
    app = FastAPI(
        title="Assessor.IA API",
        summary="Multi-agent chatbot API",
        version="2.0.0",
        description=(
            "## Assessor.IA\n\n"
            "API responsible for hosting Assessor.IA's multi-agent system.\n"
            "Assessor.IA is a chatbot that helps you with your finance and agenda."
        ),
        lifespan=lifespan,
    )
    setup_dishka(container=container or create_container(), app=app)

    register_exception_handlers(
        app,
        logger=create_logger(register_exception_handlers.__module__),
        session_context_factory=bind_session_context,
    )

    for router in ROUTES:
        app.include_router(router, prefix="/api")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "Assessor.IA API is up and running!"}

    @app.get("/")
    def root() -> FileResponse:
        return FileResponse(FRONTEND / "index.html")

    app.mount("/", StaticFiles(directory=FRONTEND))
    return app


app = create_app()
