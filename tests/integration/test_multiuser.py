from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from app.application.exceptions import TransactionNotFoundError
from app.application.models.transaction_query import TransactionQueryParams
from app.application.models.transaction_update import (
    UpdateTransactionParams,
    UpdateTransactionQuery,
)
from app.domain.model.transaction import Transaction, TransactionType
from app.infrastructure.postgres.entities.user import UserORM
from tests.user_identity import TEST_USER_ID

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("apply_migrations")]


@pytest.mark.asyncio
async def test_financial_operations_never_cross_owners(db_session, transaction_service):
    other = uuid4()
    db_session.add(UserORM(id=other))
    await db_session.flush()
    when = datetime(2026, 6, 1, 12, tzinfo=timezone.utc)
    records = []
    for owner, amount in [(TEST_USER_ID, 50), (other, 900)]:
        records.append(
            await transaction_service.add_transaction(
                Transaction(
                    user_id=owner,
                    amount=amount,
                    source_text="same lunch",
                    occurred_at=when,
                ),
                user_id=owner,
            )
        )
    await transaction_service.add_transaction(
        Transaction(
            user_id=other,
            amount=1000,
            source_text="salary",
            transaction_type=TransactionType.INCOME,
            occurred_at=when,
        ),
        user_id=other,
    )
    assert (
        await transaction_service.calculate_total_balance(user_id=TEST_USER_ID) == -50
    )
    assert (
        await transaction_service.calculate_daily_balance(
            date(2026, 6, 1), user_id=other
        )
        == 100
    )
    found = await transaction_service.search_transactions(
        TransactionQueryParams(source_text="same lunch"), user_id=TEST_USER_ID
    )
    assert [item.id for item in found] == [records[0].id]
    for changes in ({"amount": 1}, {"is_canceled": True}, {"is_canceled": False}):
        with pytest.raises(TransactionNotFoundError):
            await transaction_service.update_transaction(
                UpdateTransactionParams(
                    query=UpdateTransactionQuery(id=records[1].id), **changes
                ),
                user_id=TEST_USER_ID,
            )
    updated = await transaction_service.update_transaction(
        UpdateTransactionParams(
            query=UpdateTransactionQuery(
                match_text="same lunch", date_local=date(2026, 6, 1)
            ),
            amount=60,
        ),
        user_id=TEST_USER_ID,
    )
    assert updated.id == records[0].id
    assert await transaction_service.calculate_total_balance(user_id=other) == 100


@pytest.mark.asyncio
async def test_user_registry_persists_and_resolves_users(session_factory):
    from app.infrastructure.postgres.repositories.user_repository import (
        SQLAlchemyUserRepository,
    )

    repository = SQLAlchemyUserRepository(session_factory)
    created = await repository.create()
    assert created.id != TEST_USER_ID
    assert await repository.exists(created.id)
    assert not await repository.exists(uuid4())
    assert {user.id for user in await repository.list_users()} == {
        TEST_USER_ID,
        created.id,
    }
