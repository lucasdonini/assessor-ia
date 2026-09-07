from uuid import uuid4

import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as pg

from app.domain.model.transaction import Category, TransactionType
from app.infrastructure.postgres.entities.base import Base
from app.infrastructure.postgres.entities.transaction import TransactionORM
from tests.user_identity import TEST_USER_ID


class TestTransactionORM:
    def test_has_correct_tablename(self):
        assert TransactionORM.__tablename__ == "transactions"

    def test_extends_declarative_base(self):
        assert issubclass(TransactionORM, Base)

    def test_metadata_registered(self):
        assert "transactions" in Base.metadata.tables

    def test_id_column(self):
        col = TransactionORM.__table__.c["id"]
        assert col.primary_key is True
        assert isinstance(col.type, pg.UUID)

    def test_amount_column(self):
        col = TransactionORM.__table__.c["amount"]
        assert isinstance(col.type, sa.Numeric)
        assert col.type.precision == 14
        assert col.type.scale == 2
        assert col.nullable is False

    def test_category_column(self):
        col = TransactionORM.__table__.c["category"]
        assert isinstance(col.type, sa.Enum)
        assert col.type.name == "category_enum"
        assert col.nullable is False

    def test_category_enum_values_match_model(self):
        col = TransactionORM.__table__.c["category"]
        for v in col.type.enums:
            assert v in [e.name for e in Category], f"{v} not in Category names"

    def test_transaction_type_column(self):
        col = TransactionORM.__table__.c["transaction_type"]
        assert isinstance(col.type, sa.Enum)
        assert col.type.name == "transaction_type_enum"
        assert col.nullable is False

    def test_transaction_type_enum_values_match_model(self):
        col = TransactionORM.__table__.c["transaction_type"]
        enum_values = set(col.type.enums)
        model_values = {m.name for m in TransactionType}
        assert enum_values == model_values

    def test_description_column(self):
        col = TransactionORM.__table__.c["description"]
        assert isinstance(col.type, sa.Text)
        assert col.nullable is True

    def test_payment_method_column(self):
        col = TransactionORM.__table__.c["payment_method"]
        assert isinstance(col.type, sa.String)
        assert col.type.length == 32
        assert col.nullable is True

    def test_occurred_at_column(self):
        col = TransactionORM.__table__.c["occurred_at"]
        assert isinstance(col.type, sa.DateTime)
        assert col.type.timezone is True
        assert col.nullable is False
        assert col.server_default is not None

    def test_updated_at_column(self):
        col = TransactionORM.__table__.c["updated_at"]
        assert isinstance(col.type, sa.DateTime)
        assert col.type.timezone is True
        assert col.nullable is False
        assert col.server_default is not None

    def test_source_text_column(self):
        col = TransactionORM.__table__.c["source_text"]
        assert isinstance(col.type, sa.Text)
        assert col.nullable is False

    def test_has_occurred_at_index(self):
        indexes = {idx.name: idx for idx in TransactionORM.__table__.indexes}
        assert "idx_transactions_occurred_at" in indexes
        idx = indexes["idx_transactions_occurred_at"]
        cols = [c.name for c in idx.columns]
        assert "occurred_at" in cols

    def test_has_category_time_index(self):
        indexes = {idx.name: idx for idx in TransactionORM.__table__.indexes}
        assert "idx_transactions_category_time" in indexes
        idx = indexes["idx_transactions_category_time"]
        cols = [c.name for c in idx.columns]
        assert "category" in cols
        assert "occurred_at" in cols

    def test_create_orm_instance_minimal(self):
        orm = TransactionORM(
            amount=100.0,
            category=Category.FOOD,
            transaction_type=TransactionType.EXPENSE,
            source_text="teste",
            user_id=TEST_USER_ID,
        )
        assert orm.amount == 100.0
        assert orm.category == Category.FOOD
        assert orm.transaction_type == TransactionType.EXPENSE
        assert orm.source_text == "teste"
        assert orm.description is None
        assert orm.payment_method is None
        assert orm.id is None

    def test_create_orm_instance_full(self):
        from datetime import datetime, timezone

        uid = uuid4()
        dt = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        orm = TransactionORM(
            id=uid,
            amount=250.75,
            category=Category.HEALTH,
            transaction_type=TransactionType.INCOME,
            description="test",
            payment_method="pix",
            occurred_at=dt,
            source_text="teste",
            user_id=TEST_USER_ID,
        )
        assert orm.id == uid
        assert orm.amount == 250.75
        assert orm.description == "test"
        assert orm.payment_method == "pix"
        assert orm.occurred_at == dt
