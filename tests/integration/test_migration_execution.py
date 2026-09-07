import pytest
from sqlalchemy import inspect, text

from tests.user_identity import TEST_USER_ID

pytestmark = [
    pytest.mark.integration,
    pytest.mark.usefixtures("apply_migrations"),
]


class TestMigrationExecution:
    def test_upgrade_head_creates_transactions_table(self, migration_engine):
        inspector = inspect(migration_engine)
        tables = inspector.get_table_names()
        assert "transactions" in tables

    def test_upgrade_head_creates_category_enum(self, migration_engine):
        with migration_engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'category_enum')"  # noqa: E501
                )
            )
            assert result.scalar() is True

    def test_upgrade_head_creates_transaction_type_enum(self, migration_engine):
        with migration_engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT EXISTS ("
                    "SELECT 1 FROM pg_type WHERE typname = 'transaction_type_enum'"
                    ")"
                )
            )
            assert result.scalar() is True

    def test_transactions_columns(self, migration_engine):
        inspector = inspect(migration_engine)
        columns = {c["name"]: c for c in inspector.get_columns("transactions")}

        assert columns["id"]["type"].__class__.__name__ == "UUID"
        assert columns["amount"]["type"].__class__.__name__ == "NUMERIC"
        assert columns["category"]["type"].__class__.__name__ == "ENUM"
        assert columns["transaction_type"]["type"].__class__.__name__ == "ENUM"
        assert columns["source_text"]["type"].__class__.__name__ == "TEXT"
        assert columns["description"]["nullable"] is True
        assert columns["payment_method"]["nullable"] is True

    def test_transactions_indexes(self, migration_engine):
        inspector = inspect(migration_engine)
        indexes = {ix["name"] for ix in inspector.get_indexes("transactions")}
        assert "idx_transactions_occurred_at" in indexes
        assert "idx_transactions_category_time" in indexes

    def test_enum_values_are_correct(self, migration_engine):
        with migration_engine.connect() as conn:
            result = conn.execute(text("SELECT enum_range(NULL::category_enum)::text"))
            enum_range = result.scalar()
            assert "FOOD" in enum_range
            assert "TRANSPORTATION" in enum_range
            assert "BILLS" in enum_range
            assert "OTHER" in enum_range

    def test_dictionary_tables_do_not_exist(self, migration_engine):
        inspector = inspect(migration_engine)
        tables = inspector.get_table_names()
        assert "categories" not in tables
        assert "transaction_types" not in tables

    @pytest.mark.asyncio
    async def test_insert_and_read_transaction(self, db_session):
        from decimal import Decimal

        from app.domain.model.transaction import Category, TransactionType
        from app.infrastructure.postgres.entities.transaction import TransactionORM

        orm = TransactionORM(
            amount=Decimal("99.90"),
            category=Category.FOOD,
            transaction_type=TransactionType.EXPENSE,
            source_text="teste insert",
            user_id=TEST_USER_ID,
        )
        db_session.add(orm)
        await db_session.commit()

        fetched = await db_session.get(TransactionORM, orm.id)
        assert fetched is not None
        assert fetched.amount == Decimal("99.90")
        assert fetched.category == Category.FOOD

    @pytest.mark.asyncio
    async def test_insert_with_enum_filter(self, db_session):
        from sqlalchemy import select

        from app.domain.model.transaction import Category, TransactionType
        from app.infrastructure.postgres.entities.transaction import TransactionORM

        db_session.add_all(
            [
                TransactionORM(
                    amount=10,
                    category=Category.FOOD,
                    transaction_type=TransactionType.EXPENSE,
                    source_text="food1",
                    user_id=TEST_USER_ID,
                ),
                TransactionORM(
                    amount=20,
                    category=Category.HEALTH,
                    transaction_type=TransactionType.EXPENSE,
                    source_text="health1",
                    user_id=TEST_USER_ID,
                ),
            ]
        )
        await db_session.commit()

        stmt = select(TransactionORM).where(TransactionORM.category == Category.HEALTH)
        results = (await db_session.scalars(stmt)).all()
        assert len(results) == 1
        assert results[0].source_text == "health1"
