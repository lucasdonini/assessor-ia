from collections.abc import AsyncGenerator, AsyncIterator, Generator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from unittest.mock import patch

import pytest
import pytest_asyncio
from alembic.command import downgrade, upgrade
from alembic.config import Config as AlembicConfig
from pydantic import SecretStr
from sqlalchemy import Engine, create_engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from testcontainers.community.postgres import PostgresContainer

from app.domain.model.transaction import Category, TransactionType
from app.infrastructure.postgres.entities.transaction import TransactionORM
from app.infrastructure.postgres.entities.user import UserORM
from app.infrastructure.postgres.pg_connection import (
    build_async_postgres_url,
    build_sync_postgres_url,
)
from app.infrastructure.postgres.repositories.transaction_repository import (
    SQLAlchemyTransactionRepository,
)
from app.services.transaction_service import TransactionService
from tests.user_identity import TEST_USER_ID

ALEMBIC_CFG = AlembicConfig(str(Path(__file__).resolve().parent.parent / "alembic.ini"))


@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer, None, None]:
    with PostgresContainer("postgres:16-alpine") as container:
        yield container


@pytest.fixture(scope="session")
def db_url(postgres_container: PostgresContainer) -> str:
    return postgres_container.get_connection_url()


@pytest.fixture(scope="session")
def apply_migrations(db_url: str) -> Generator[None, None, None]:
    with patch("app.infrastructure.settings.settings.postgres_url", SecretStr(db_url)):
        upgrade(ALEMBIC_CFG, "head")
        yield
        downgrade(ALEMBIC_CFG, "base")


@pytest_asyncio.fixture
async def raw_engine(db_url: str) -> AsyncGenerator[AsyncEngine]:
    engine = create_async_engine(build_async_postgres_url(db_url), pool_pre_ping=True)
    yield engine
    await engine.dispose()


@pytest.fixture
def migration_engine(db_url: str) -> Generator[Engine]:
    engine = create_engine(build_sync_postgres_url(db_url), pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest_asyncio.fixture
async def db_session(raw_engine: AsyncEngine) -> AsyncGenerator[AsyncSession]:
    connection = await raw_engine.connect()
    transaction = await connection.begin()
    session = AsyncSession(bind=connection, expire_on_commit=False)

    session.add(UserORM(id=TEST_USER_ID))
    await session.flush()
    yield session

    await session.close()
    if transaction.is_active:
        await transaction.rollback()
    await connection.close()


@pytest.fixture
def session_factory(
    db_session: AsyncSession,
) -> Callable[[], AsyncIterator[AsyncSession]]:
    @asynccontextmanager
    async def factory() -> AsyncIterator[AsyncSession]:
        yield db_session

    return factory


@pytest.fixture
def transaction_repository(session_factory) -> SQLAlchemyTransactionRepository:
    return SQLAlchemyTransactionRepository(session_factory=session_factory)


@pytest.fixture
def transaction_service(transaction_repository, mock_logger) -> TransactionService:
    return TransactionService(
        repository=transaction_repository,
        logger=mock_logger,
    )


async def _insert_seed_transactions(
    session: AsyncSession,
) -> list[TransactionORM]:
    seeds = [
        TransactionORM(
            amount=5000.00,
            category=Category.OTHER,
            transaction_type=TransactionType.INCOME,
            description="Salário",
            occurred_at=datetime(2026, 6, 1, 8, 0, 0, tzinfo=timezone.utc),
            source_text="Recebi salário de 5000 reais",
            user_id=TEST_USER_ID,
        ),
        TransactionORM(
            amount=150.00,
            category=Category.FOOD,
            transaction_type=TransactionType.EXPENSE,
            description="Almoço",
            occurred_at=datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
            source_text="Gastei 150 reais com almoço",
            user_id=TEST_USER_ID,
        ),
        TransactionORM(
            amount=3000.00,
            category=Category.OTHER,
            transaction_type=TransactionType.INCOME,
            description="Freela",
            occurred_at=datetime(2026, 6, 2, 14, 0, 0, tzinfo=timezone.utc),
            source_text="Recebi 3000 de freela",
            user_id=TEST_USER_ID,
        ),
        TransactionORM(
            amount=50.00,
            category=Category.TRANSPORTATION,
            transaction_type=TransactionType.EXPENSE,
            description="Uber",
            occurred_at=datetime(2026, 6, 2, 18, 0, 0, tzinfo=timezone.utc),
            source_text="Gastei 50 de uber",
            user_id=TEST_USER_ID,
        ),
        TransactionORM(
            amount=200.00,
            category=Category.HEALTH,
            transaction_type=TransactionType.EXPENSE,
            description="Farmácia",
            occurred_at=datetime(2026, 6, 3, 10, 0, 0, tzinfo=timezone.utc),
            source_text="Comprei remedio",
            user_id=TEST_USER_ID,
        ),
        TransactionORM(
            amount=1000.00,
            category=Category.INVESTMENT,
            transaction_type=TransactionType.TRANSFER,
            description="Investimento",
            occurred_at=datetime(2026, 6, 3, 16, 0, 0, tzinfo=timezone.utc),
            source_text="Transferi 1000 para investimentos",
            user_id=TEST_USER_ID,
        ),
    ]
    session.add_all(seeds)
    await session.commit()
    for orm in seeds:
        await session.refresh(orm)
    return seeds


@pytest_asyncio.fixture
async def seed_transactions(db_session: AsyncSession) -> list[TransactionORM]:
    return await _insert_seed_transactions(db_session)
