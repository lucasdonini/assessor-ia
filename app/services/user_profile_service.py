import asyncio
from dataclasses import replace
from uuid import UUID

from app.application.exceptions import ProfileUnavailableError
from app.application.ports.logger import Logger, LoggerFactory
from app.application.ports.profile_preferences_index import ProfilePreferencesIndex
from app.application.repositories.user_profile_repository import UserProfileRepository
from app.domain.model.user_profile import UserProfile


class UserProfileService:
    def __init__(
        self,
        *,
        repository: UserProfileRepository,
        index: ProfilePreferencesIndex,
        logger_factory: LoggerFactory,
    ) -> None:
        self._repository = repository
        self._index = index
        self._logger: Logger = logger_factory(__name__)
        # One shared application instance serializes the two-store operations.
        self._lock = asyncio.Lock()

    async def save(self, profile: UserProfile) -> UserProfile:
        try:
            async with self._lock:
                await self._repository.upsert(profile)
                await self._index.upsert(profile.preferences, user_id=profile.user_id)
            return profile
        except Exception as error:
            self._logger.exception("Profile save failed", exception=error)
            raise ProfileUnavailableError() from error

    async def consult(self, query: str, *, user_id: UUID) -> UserProfile | None:
        try:
            async with self._lock:
                profile = await self._repository.find_by_user_id(user_id)
                if profile is None:
                    return None
                if profile.user_id != user_id:
                    raise ValueError("Unexpected profile owner")
                matches = await self._index.search(query, user_id=user_id)
                if matches != [profile.preferences]:
                    raise ValueError("Profile preferences index is not synchronized")
                return replace(profile, preferences=matches[0])
        except Exception as error:
            self._logger.exception("Profile consultation failed", exception=error)
            raise ProfileUnavailableError() from error
