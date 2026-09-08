from .chat import router as chat_router
from .profile import router as profile_router
from .session import router as session_router
from .user import router as user_router

ROUTES = [chat_router, profile_router, session_router, user_router]

__all__ = ["ROUTES"]
