import asyncio
from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.application.exceptions import (
    EvidenceRejectedError,
    FinancialOutcomeUnknownError,
    UnsupportedCurrencyError,
)
from app.application.models.currency import brl_statement, explicit_brl
from app.application.models.evidence import FinancialExecution, Judgment
from app.application.models.transaction_update import (
    UpdateTransactionParams,
    UpdateTransactionQuery,
)
from app.domain.model.transaction import Transaction
from app.services.transaction_service import TransactionService


@pytest.mark.parametrize(
    "text,amount,valid",
    [
        ("Foram 120 reais", 120, True),
        ("Paguei R$ 1.200,50", 1200.50, True),
        ("BRL 30", 30, True),
        ("Comprei por 30 dólares", 30, False),
        ("Comprei por 30", 30, False),
        ("Paguei $30", 30, False),
        ("Paguei 30 reais", 40, False),
        ("R$ 10 e R$ 20", 10, False),
        ("R$ 30 ou USD 30", 30, False),
        ("R$ -30", 30, False),
    ],
)
def test_currency_is_deterministic(text, amount, valid):
    assert explicit_brl(text, amount) is valid


@pytest.mark.parametrize("followups", [("Sim",), ("Sim", "120"), ("Sim", "120", "120")])
@pytest.mark.asyncio
async def test_reported_zara_confirmation_keeps_original_amount_and_source(
    setup, followups
):
    service, repo, validator, user, transaction = setup
    original = "Comprei uma camisa na Zara por 120 reais"
    execution = FinancialExecution(user, (original, *followups))
    await service.add_transaction(transaction, user_id=user, execution=execution)
    repo.add_transaction.assert_awaited_once()
    assert repo.add_transaction.call_args.args[0].source_text == original
    request = validator.validate.call_args.args[0]
    assert request.statements == (original, *followups)
    assert execution.receipts == ["Lançamento registrado em BRL."]


@pytest.mark.parametrize(
    "statements",
    [
        ("Comprei por 120 reais", "Quanto é o dólar?", "Sim"),
        ("Comprei por 120 reais", "Comprei por 120 dólares", "Sim"),
        ("Comprei por 120 reais", "Comprei por 200 reais", "Sim"),
        ("Comprei por 120 reais", "200", "Sim"),
        ("Comprei por 120 reais", "Não registre", "Sim"),
        ("Comprei por 120 reais", "Comprei outra camisa", "Sim"),
        ("Sim", "120"),
        ("Comprei por 120 reais", "Sim", "Sim", "Sim", "Sim", "Sim", "Sim"),
    ],
)
def test_confirmation_never_reuses_unrelated_or_out_of_window_amount(statements):
    assert brl_statement(statements, 120) is None


@pytest.mark.asyncio
async def test_confirmation_does_not_bypass_judge_refusal(setup):
    service, repo, validator, user, transaction = setup
    validator.validate.return_value = Judgment(reason="unsupported")
    with pytest.raises(EvidenceRejectedError):
        await service.add_transaction(
            transaction,
            user_id=user,
            execution=FinancialExecution(user, ("Comprei por 120 reais", "Sim")),
        )
    repo.add_transaction.assert_not_awaited()


@pytest.fixture
def setup():
    repo = AsyncMock()
    validator = AsyncMock()
    validator.validate.return_value = Judgment(approved=True, reason="approved")
    user = uuid4()
    transaction = Transaction(
        user_id=user, amount=120, source_text="model invented source"
    )
    repo.add_transaction.return_value = replace(transaction, id=uuid4())
    repo.update_transaction.return_value = replace(transaction, id=uuid4())
    repo.resolve_transaction.return_value = transaction
    return (
        TransactionService(repo, lambda _: MagicMock(), validator),
        repo,
        validator,
        user,
        transaction,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text", ["30 dólares", "camisa", "Foram 120", "Foram 999 reais"]
)
async def test_rejected_amount_never_writes(setup, text):
    service, repo, validator, user, transaction = setup
    execution = FinancialExecution(user, (text,))
    with pytest.raises(UnsupportedCurrencyError):
        await service.add_transaction(transaction, user_id=user, execution=execution)
    repo.add_transaction.assert_not_awaited()
    validator.validate.assert_not_awaited()
    assert execution.receipts and execution.stopped


@pytest.mark.asyncio
async def test_missing_context_and_failed_judge_never_write(setup):
    service, repo, validator, user, transaction = setup
    with pytest.raises(EvidenceRejectedError):
        await service.add_transaction(transaction, user_id=user)
    validator.validate.return_value = Judgment(reason="unavailable")
    with pytest.raises(EvidenceRejectedError):
        await service.add_transaction(
            transaction,
            user_id=user,
            execution=FinancialExecution(user, ("Foram 120 reais",)),
        )
    repo.add_transaction.assert_not_awaited()


@pytest.mark.asyncio
async def test_committed_receipt_and_concurrent_duplicate(setup):
    service, repo, validator, user, transaction = setup
    execution = FinancialExecution(user, ("Comprei camisa na Zara", "Foram 120 reais"))

    async def write():
        return await service.add_transaction(
            transaction, user_id=user, execution=execution
        )

    results = await asyncio.gather(write(), write())
    assert results[0] == results[1]
    repo.add_transaction.assert_awaited_once()
    validator.validate.assert_awaited_once()
    assert execution.receipts == ["Lançamento registrado em BRL."]
    assert repo.add_transaction.call_args.args[0].source_text == "Foram 120 reais"


@pytest.mark.asyncio
async def test_later_uncertain_operation_preserves_prior_receipt(setup):
    service, repo, validator, user, transaction = setup
    execution = FinancialExecution(user, ("Foram 120 reais",))
    await service.add_transaction(transaction, user_id=user, execution=execution)
    repo.update_transaction.side_effect = TimeoutError()
    with pytest.raises(FinancialOutcomeUnknownError):
        await service.update_transaction(
            UpdateTransactionParams(
                query=UpdateTransactionQuery(id=uuid4()), is_canceled=True
            ),
            user_id=user,
            execution=execution,
        )
    assert execution.receipts[0] == "Lançamento registrado em BRL."
    assert "Verifique" in execution.receipts[1]
    assert execution.stopped


@pytest.mark.asyncio
async def test_other_user_context_cannot_mutate(setup):
    service, repo, validator, user, transaction = setup
    with pytest.raises(EvidenceRejectedError):
        await service.add_transaction(
            transaction,
            user_id=user,
            execution=FinancialExecution(uuid4(), ("120 reais",)),
        )
    repo.add_transaction.assert_not_awaited()


@pytest.mark.asyncio
async def test_cancel_does_not_require_repeating_currency(setup):
    service, repo, validator, user, transaction = setup
    execution = FinancialExecution(user, ("Cancele esse lançamento",))
    await service.update_transaction(
        UpdateTransactionParams(
            query=UpdateTransactionQuery(id=uuid4()), is_canceled=True
        ),
        user_id=user,
        execution=execution,
    )
    assert execution.receipts == ["Lançamento cancelado."]


@pytest.mark.asyncio
async def test_cannot_implicitly_convert_legacy_foreign_record(setup):
    service, repo, validator, user, transaction = setup
    repo.resolve_transaction.return_value = replace(
        transaction, source_text="120 dólares"
    )
    with pytest.raises(UnsupportedCurrencyError):
        await service.update_transaction(
            UpdateTransactionParams(
                query=UpdateTransactionQuery(id=uuid4()), amount=50
            ),
            user_id=user,
            execution=FinancialExecution(user, ("Altere para 50 reais",)),
        )
    validator.validate.assert_not_awaited()
    repo.update_transaction.assert_not_awaited()
