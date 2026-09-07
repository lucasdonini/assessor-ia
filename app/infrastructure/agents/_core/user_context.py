from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from app.application.models.user_context import UserContext

_context: ContextVar[UserContext] = ContextVar("agent_user_context")


def get_user_context() -> UserContext:
    """Return server-provided identity, never model-supplied tool arguments."""
    return _context.get()


@contextmanager
def bind_user_context(context: UserContext) -> Iterator[None]:
    token = _context.set(context)
    try:
        yield
    finally:
        _context.reset(token)
