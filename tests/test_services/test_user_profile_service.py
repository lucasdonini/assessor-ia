from dataclasses import replace
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.application.exceptions import ProfileUnavailableError
from app.domain.model.user_profile import RiskTolerance, UserProfile
from app.services.user_profile_service import UserProfileService


@pytest.mark.asyncio
async def test_partial_failure_can_be_retried_and_stale_preferences_are_refused() -> (
    None
):
    profile = UserProfile(uuid4(), Decimal("42"), "Trip", RiskTolerance.LOW, "Safe")
    repository, index = AsyncMock(), AsyncMock()
    repository.find_by_user_id.return_value = profile
    index.upsert.side_effect = [RuntimeError("private backend detail"), None]
    service = UserProfileService(repository=repository, index=index, logger=MagicMock())
    with pytest.raises(ProfileUnavailableError):
        await service.save(profile)
    assert await service.save(profile) == profile
    assert repository.upsert.await_count == 2
    index.search.return_value = ["old preferences"]
    with pytest.raises(ProfileUnavailableError):
        await service.consult("crypto", user_id=profile.user_id)
    index.search.return_value = [profile.preferences]
    assert await service.consult("crypto", user_id=profile.user_id) == profile
    index.search.assert_awaited_with("crypto", user_id=profile.user_id)
    repository.find_by_user_id.return_value = replace(profile, user_id=uuid4())
    with pytest.raises(ProfileUnavailableError):
        await service.consult("crypto", user_id=profile.user_id)


@pytest.mark.asyncio
async def test_missing_profile_does_not_query_or_populate_index() -> None:
    repository, index = AsyncMock(), AsyncMock()
    repository.find_by_user_id.return_value = None
    service = UserProfileService(repository=repository, index=index, logger=MagicMock())
    assert await service.consult("saving", user_id=uuid4()) is None
    index.search.assert_not_called()
    index.upsert.assert_not_called()
