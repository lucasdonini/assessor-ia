from dishka import AsyncContainer, make_async_container

from .providers import ApplicationProvider


def create_container() -> AsyncContainer:
    return make_async_container(ApplicationProvider())
