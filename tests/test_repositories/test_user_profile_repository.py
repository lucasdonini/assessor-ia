from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.domain.model.user_profile import RiskTolerance, UserProfile
from app.infrastructure.mongodb.entities.user_profile import UserProfileDocument
from app.infrastructure.mongodb.repositories.user_profile_repository import (
    BeanieUserProfileRepository,
)


@pytest.mark.asyncio
async def test_upsert_replaces_the_same_user_document() -> None:
    profile = UserProfile(
        uuid4(), Decimal("4200.01"), "Trip", RiskTolerance.LOW, "Safe"
    )
    collection = AsyncMock()
    with patch.object(
        UserProfileDocument, "get_pymongo_collection", return_value=collection
    ):
        repository = BeanieUserProfileRepository()
        await repository.upsert(profile)
        await repository.upsert(profile)
    assert collection.replace_one.await_count == 2
    args, kwargs = collection.replace_one.call_args
    assert args[0] == {"_id": str(profile.user_id)}
    assert args[1]["monthly_revenue"] == "4200.01"
    assert args[1]["preferences"] == "Safe"
    assert kwargs == {"upsert": True}


@pytest.mark.asyncio
async def test_read_is_scoped_to_primary_key() -> None:
    user_id = uuid4()
    with patch.object(UserProfileDocument, "get", new_callable=AsyncMock) as get:
        get.return_value = None
        assert await BeanieUserProfileRepository().find_by_user_id(user_id) is None
        get.assert_awaited_once_with(str(user_id))
