from .agenda import router as agenda_router
from .auth import router as auth_router
from .chat import router as chat_router
from .monitor import router as monitor_router
from .profile import router as profile_router
from .session import router as session_router

ROUTES = [
    chat_router,
    profile_router,
    session_router,
    auth_router,
    agenda_router,
    monitor_router,
]

__all__ = ["ROUTES"]
