import asyncio
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
import pytest_asyncio
from alembic.command import upgrade
from alembic.config import Config
from pydantic import SecretStr
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from testcontainers.community.postgres import PostgresContainer

from app.application.models.event_query import EventQuery
from app.domain.model.event import EventDraft
from app.infrastructure.postgres.entities.event import EventOperationORM, EventORM
from app.infrastructure.postgres.entities.user import UserORM
from app.infrastructure.postgres.pg_connection import build_async_postgres_url
from app.infrastructure.postgres.repositories.auth_repository import (
    SQLAlchemyAuthRepository,
)
from app.infrastructure.postgres.repositories.event_repository import (
    InvalidEventProposal,
    SQLAlchemyEventRepository,
)

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def agenda_database():
    # Isolate committed concurrency tests from the legacy suite's shared database.
    with PostgresContainer("postgres:16-alpine") as container:
        url = container.get_connection_url()
        with patch("app.infrastructure.settings.settings.postgres_url", SecretStr(url)):
            upgrade(Config(str(Path(__file__).parents[2] / "alembic.ini")), "head")
        yield url


@pytest_asyncio.fixture
async def raw_engine(agenda_database):
    engine = create_async_engine(build_async_postgres_url(agenda_database))
    try:
        yield engine
    finally:
        await engine.dispose()


def draft(start="2026-10-27T14:00:00-03:00", end="2026-10-27T15:00:00-03:00"):
    return EventDraft(
        title="Dentista", source_text="dentista", start_time=start, end_time=end
    )


@pytest.mark.asyncio
async def test_owned_conflicts_concurrency_confirmation_and_repetition(raw_engine):
    factory = async_sessionmaker(raw_engine, expire_on_commit=False)
    a, b = uuid4(), uuid4()
    async with factory.begin() as session:
        session.add_all([UserORM(id=a), UserORM(id=b)])
    repository = SQLAlchemyEventRepository(factory)
    op1, op2 = uuid4(), uuid4()
    first, second = await asyncio.gather(
        repository.create(a, op1, draft()), repository.create(a, op2, draft())
    )
    assert sum(created for _, created in (first, second)) == 1
    pending = next(result for result, created in (first, second) if not created)
    assert pending.requires_confirmation and pending.event is None
    assert len(pending.conflicts) == 1
    assert await repository.query(b, EventQuery()) == []
    assert await repository.operation(b, pending.operation_id) is None
    with pytest.raises(InvalidEventProposal):
        await repository.create(b, pending.operation_id, draft(), confirm=True)
    confirmed, created = await repository.create(
        a, pending.operation_id, draft(), confirm=True
    )
    assert created and confirmed.event is not None
    repeated, created_again = await repository.create(
        a, pending.operation_id, draft(), confirm=True
    )
    assert not created_again and repeated.event.id == confirmed.event.id
    assert len(await repository.query(a, EventQuery(text="DENTISTA"))) == 2


@pytest.mark.asyncio
async def test_local_date_boundaries_and_prior_day_conflicts(raw_engine):
    factory = async_sessionmaker(raw_engine, expire_on_commit=False)
    owner = uuid4()
    async with factory.begin() as session:
        session.add(UserORM(id=owner))
    repository = SQLAlchemyEventRepository(factory)
    overnight = draft("2026-10-27T23:30:00-03:00", "2026-10-28T01:00:00-03:00")
    await repository.create(owner, uuid4(), overnight)
    assert len(await repository.query(owner, EventQuery(date_local="2026-10-27"))) == 1
    assert await repository.query(owner, EventQuery(date_local="2026-10-28")) == []
    conflict, created = await repository.create(
        owner, uuid4(), draft("2026-10-28T00:00:00-03:00", "2026-10-28T00:30:00-03:00")
    )
    assert not created and conflict.requires_confirmation
    adjacent, created = await repository.create(
        owner, uuid4(), draft("2026-10-28T01:00:00-03:00", "2026-10-28T02:00:00-03:00")
    )
    assert created and adjacent.event


@pytest.mark.asyncio
async def test_expired_and_changed_conflicts_cannot_bypass_confirmation(raw_engine):
    factory = async_sessionmaker(raw_engine, expire_on_commit=False)
    owner = uuid4()
    async with factory.begin() as session:
        session.add(UserORM(id=owner))
    repository = SQLAlchemyEventRepository(factory)
    await repository.create(owner, uuid4(), draft())
    pending, _ = await repository.create(owner, uuid4(), draft())
    another, _ = await repository.create(owner, uuid4(), draft())
    await repository.create(owner, another.operation_id, draft(), confirm=True)
    changed, created = await repository.create(
        owner, pending.operation_id, draft(), confirm=True
    )
    assert not created and len(changed.conflicts) == 2
    async with factory.begin() as session:
        await session.execute(
            update(EventOperationORM)
            .where(EventOperationORM.id == pending.operation_id)
            .values(expires_at=datetime(2000, 1, 1, tzinfo=UTC))
        )
    with pytest.raises(InvalidEventProposal):
        await repository.create(owner, pending.operation_id, draft(), confirm=True)
    async with factory() as session:
        assert (
            await session.scalar(
                select(func.count())
                .select_from(EventORM)
                .where(EventORM.user_id == owner)
            )
            == 2
        )


@pytest.mark.asyncio
async def test_verified_identity_never_claims_existing_demo_user(raw_engine):
    factory = async_sessionmaker(raw_engine, expire_on_commit=False)
    legacy = uuid4()
    async with factory.begin() as session:
        session.add(UserORM(id=legacy))
    repository = SQLAlchemyAuthRepository(factory)
    subject = "synthetic-" + str(uuid4())
    first, second = await asyncio.gather(
        repository.resolve_identity(subject), repository.resolve_identity(subject)
    )
    assert first == second and first != legacy
    async with factory() as session:
        assert await session.get(UserORM, legacy) is not None
