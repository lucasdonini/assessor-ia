from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from alembic.command import upgrade
from alembic.config import Config
from pydantic import SecretStr
from sqlalchemy import create_engine, text
from testcontainers.community.postgres import PostgresContainer

from app.infrastructure.postgres.pg_connection import build_sync_postgres_url

pytestmark = pytest.mark.integration


def test_additive_migrations_preserve_populated_previous_schema():
    # Dedicated disposable database: never use application settings as a target.
    with PostgresContainer("postgres:16-alpine") as container:
        url = container.get_connection_url()
        config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
        with patch("app.infrastructure.settings.settings.postgres_url", SecretStr(url)):
            upgrade(config, "b21b30c40d50")
            engine = create_engine(build_sync_postgres_url(url))
            owner, transaction = uuid4(), uuid4()
            try:
                with engine.begin() as connection:
                    connection.execute(
                        text("INSERT INTO users(id) VALUES (:id)"), {"id": owner}
                    )
                    connection.execute(
                        text(
                            "INSERT INTO transactions(id, user_id, amount, category, "
                            "transaction_type, source_text) VALUES "
                            "(:id, :user, 42, 'OTHER', 'EXPENSE', "
                            "'synthetic legacy record')"
                        ),
                        {"id": transaction, "user": owner},
                    )
                upgrade(config, "head")
                with engine.connect() as connection:
                    row = connection.execute(
                        text("SELECT user_id, amount FROM transactions WHERE id=:id"),
                        {"id": transaction},
                    ).one()
                    assert row.user_id == owner and row.amount == 42
                    assert (
                        connection.scalar(
                            text("SELECT count(*) FROM google_identities")
                        )
                        == 0
                    )
                    assert connection.scalar(text("SELECT count(*) FROM events")) == 0
            finally:
                engine.dispose()
