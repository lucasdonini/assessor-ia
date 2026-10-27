import pytest

from app.application.exceptions import UnsupportedCurrencyError
from app.application.models.evidence import FinancialExecution
from app.application.models.transaction_query import TransactionQueryParams
from app.domain.model.transaction import Transaction
from app.infrastructure.agents._core.evidence import evidence_execution
from app.infrastructure.agents._core.schemas.tool_response import ToolFailure
from app.infrastructure.agents.tools.add_transaction import AddTransactionTool
from tests.user_identity import TEST_USER_ID

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio,
    pytest.mark.usefixtures("apply_migrations"),
]


@pytest.mark.parametrize("followups", [("Sim",), ("Sim", "120", "120")])
async def test_confirmed_purchase_persists_original_brl_evidence(
    transaction_service, followups
):
    original = "Comprei uma camisa na Zara por 120 reais"
    execution = FinancialExecution(TEST_USER_ID, (original, *followups))
    await transaction_service.add_transaction(
        Transaction(user_id=TEST_USER_ID, amount=120, source_text="Sim"),
        user_id=TEST_USER_ID,
        execution=execution,
    )
    records = await transaction_service.search_transactions(
        TransactionQueryParams(limit=None),
        user_id=TEST_USER_ID,
    )
    assert len(records) == 1
    assert records[0].amount == 120
    assert records[0].source_text == original
    assert execution.receipts == ["Lançamento registrado em BRL."]


async def test_foreign_amount_is_not_inserted(transaction_service, db_session):
    before = await transaction_service.search_transactions(
        TransactionQueryParams(limit=None), user_id=TEST_USER_ID
    )
    execution = FinancialExecution(TEST_USER_ID, ("Comprei camisa por 30 dólares",))
    with pytest.raises(UnsupportedCurrencyError):
        await transaction_service.add_transaction(
            Transaction(user_id=TEST_USER_ID, amount=30, source_text="R$ 30 invented"),
            user_id=TEST_USER_ID,
            execution=execution,
        )
    after = await transaction_service.search_transactions(
        TransactionQueryParams(limit=None), user_id=TEST_USER_ID
    )
    assert after == before == []


async def test_legacy_brl_default_and_full_scope_foreign_guard(transaction_repository):
    for index in range(55):
        await transaction_repository.add_transaction(
            Transaction(
                user_id=TEST_USER_ID, amount=1, source_text=f"legacy item {index}"
            ),
            user_id=TEST_USER_ID,
        )
    assert await transaction_repository.get_balance(user_id=TEST_USER_ID) == -55
    foreign = await transaction_repository.add_transaction(
        Transaction(user_id=TEST_USER_ID, amount=30, source_text="30 dólares"),
        user_id=TEST_USER_ID,
    )
    with pytest.raises(UnsupportedCurrencyError):
        await transaction_repository.get_balance(user_id=TEST_USER_ID)
    records = await transaction_repository.find(
        TransactionQueryParams(limit=None), user_id=TEST_USER_ID
    )
    assert len(records) == 56
    assert any(item.id == foreign.id and item.amount == 30 for item in records)


async def test_missing_execution_cannot_bypass_through_tool(
    transaction_service, mock_logger_factory
):
    tool = AddTransactionTool(
        service=transaction_service, logger_factory=mock_logger_factory
    )
    with evidence_execution(TEST_USER_ID, ()):
        result = await tool._arun(
            transaction={"amount": 120, "source_text": "120 reais"}
        )
    assert isinstance(result, ToolFailure)
    assert result.code == "evidence_rejected"
    assert (
        await transaction_service.search_transactions(
            TransactionQueryParams(limit=None), user_id=TEST_USER_ID
        )
        == []
    )
