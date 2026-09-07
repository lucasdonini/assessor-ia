from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, create_autospec
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.user_identity import TEST_USER_ID


def _patch_create_agent_model_edge():
    """Fix LangChain + LangGraph 1.1.6 incompatibility in `create_agent`."""
    import langchain.agents.factory as factory

    original = factory._make_model_to_tools_edge

    def _patched_make_edge(
        *, model_destination, structured_output_tools, end_destination
    ):
        edge_fn = original(
            model_destination=model_destination,
            structured_output_tools=structured_output_tools,
            end_destination=end_destination,
        )

        def _safe_edge(state):
            result = edge_fn(state)
            if isinstance(result, str) and result == model_destination:
                return end_destination
            return result

        return _safe_edge

    factory._make_model_to_tools_edge = _patched_make_edge


_patch_create_agent_model_edge()

pytest_plugins = ["tests.conftest_integration"]  # noqa: E402

from app.application.models.transaction_query import (  # noqa: E402
    TransactionQueryParams,
)
from app.application.models.transaction_update import (  # noqa: E402
    UpdateTransactionParams,
    UpdateTransactionQuery,
)
from app.application.ports.logger import Logger  # noqa: E402
from app.application.repositories.transaction_repository import (  # noqa: E402
    TransactionRepository,
)
from app.domain.model.transaction import (  # noqa: E402
    Category,
    Transaction,
    TransactionType,
)
from app.infrastructure.postgres.repositories.transaction_repository import (  # noqa: E402
    SQLAlchemyTransactionRepository,
)
from app.services.transaction_service import TransactionService  # noqa: E402


@pytest.fixture
def sample_transaction() -> Transaction:
    return Transaction(
        amount=150.50,
        category=Category.FOOD,
        transaction_type=TransactionType.EXPENSE,
        description="Almoço no restaurante",
        payment_method="dinheiro",
        occurred_at=datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
        source_text="Gastei 150 reais com almoço",
        is_canceled=False,
        user_id=TEST_USER_ID,
    )


@pytest.fixture
def sample_transaction_with_id(sample_transaction) -> Transaction:
    return Transaction(
        amount=sample_transaction.amount,
        source_text=sample_transaction.source_text,
        category=sample_transaction.category,
        transaction_type=sample_transaction.transaction_type,
        description=sample_transaction.description,
        payment_method=sample_transaction.payment_method,
        occurred_at=datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
        is_canceled=sample_transaction.is_canceled,
        user_id=TEST_USER_ID,
    )


@pytest.fixture
def sample_query_params() -> TransactionQueryParams:
    return TransactionQueryParams(
        source_text="almoço",
        occurred_at_start=date(2026, 1, 1),
        occurred_at_end=date(2026, 12, 31),
        category=Category.FOOD,
        transaction_type=TransactionType.EXPENSE,
        limit=10,
    )


@pytest.fixture
def sample_update_params_by_id() -> UpdateTransactionParams:
    return UpdateTransactionParams(
        query=UpdateTransactionQuery(id=uuid4()),
        amount=200.00,
        description="Atualizado",
    )


@pytest.fixture
def sample_update_params_by_match() -> UpdateTransactionParams:
    return UpdateTransactionParams(
        query=UpdateTransactionQuery(
            match_text="almoço",
            date_local=date(2026, 6, 1),
        ),
        amount=200.00,
    )


@pytest.fixture
def sample_update_params_empty() -> UpdateTransactionParams:
    return UpdateTransactionParams(
        query=UpdateTransactionQuery(
            match_text="almoço",
            date_local=date(2026, 6, 1),
        ),
    )


@pytest.fixture
def mock_session() -> AsyncMock:
    session = create_autospec(AsyncSession, instance=True)
    session.__aenter__.return_value = session
    session.scalars.return_value = MagicMock()
    return session


@pytest.fixture
def mock_session_factory(mock_session: AsyncMock) -> MagicMock:
    return MagicMock(return_value=mock_session)


@pytest.fixture
def repository(mock_session_factory) -> SQLAlchemyTransactionRepository:
    return SQLAlchemyTransactionRepository(session_factory=mock_session_factory)


@pytest.fixture
def mock_repository() -> MagicMock:
    return create_autospec(TransactionRepository, instance=True)


@pytest.fixture
def mock_logger() -> MagicMock:
    return create_autospec(Logger, instance=True)


@pytest.fixture
def mock_logger_factory(mock_logger: MagicMock) -> MagicMock:
    def factory(module_name: str) -> Logger:
        return mock_logger

    return create_autospec(factory, side_effect=factory)


@pytest.fixture
def service(mock_repository: MagicMock, mock_logger: MagicMock) -> TransactionService:
    return TransactionService(repository=mock_repository, logger=mock_logger)


@pytest.fixture
def sample_transactions_list() -> list[Transaction]:
    return [
        Transaction(
            amount=1000.00,
            category=Category.OTHER,
            transaction_type=TransactionType.INCOME,
            description="Salário",
            occurred_at=datetime(2026, 6, 1, 8, 0, 0, tzinfo=timezone.utc),
            source_text="Recebi salário",
            user_id=TEST_USER_ID,
        ),
        Transaction(
            amount=50.00,
            category=Category.FOOD,
            transaction_type=TransactionType.EXPENSE,
            description="Jantar",
            occurred_at=datetime(2026, 6, 2, 20, 0, 0, tzinfo=timezone.utc),
            source_text="Gastei 50 no jantar",
            user_id=TEST_USER_ID,
        ),
    ]


@pytest.fixture(autouse=True)
def tool_user_context():
    from app.application.models.user_context import UserContext
    from app.infrastructure.agents._core.user_context import bind_user_context

    with bind_user_context(UserContext(TEST_USER_ID)):
        yield
