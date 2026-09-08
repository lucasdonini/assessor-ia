import pytest

from app.infrastructure.agents.agenda.agenda_prompt import build_agenda_prompt
from app.infrastructure.agents.financial.financial_prompt import build_financial_prompt


@pytest.mark.parametrize("history_name", ["search_history", "custom_memory_lookup"])
def test_financial_prompt_uses_injected_tool_names(history_name: str) -> None:
    prompt = build_financial_prompt(
        add_transaction_tool_name="custom_add",
        daily_balance_tool_name="custom_daily",
        delete_transaction_tool_name="custom_delete",
        restore_transaction_tool_name="custom_restore",
        search_transactions_tool_name="custom_transactions",
        total_balance_tool_name="custom_balance",
        update_transaction_tool_name="custom_update",
        search_history_tool_name=history_name,
        consult_profile_tool_name="custom_profile",
    )

    for name in (
        "custom_add",
        "custom_profile",
        "custom_daily",
        "custom_delete",
        "custom_restore",
        "custom_transactions",
        "custom_balance",
        "custom_update",
        history_name,
    ):
        assert name in prompt
    assert "{search_history_tool_name}" not in prompt
    if history_name != "search_history":
        assert "search_history" not in prompt


@pytest.mark.parametrize("history_name", ["search_history", "custom_memory_lookup"])
def test_agenda_prompt_uses_injected_history_tool_name(history_name: str) -> None:
    prompt = build_agenda_prompt(search_history_tool_name=history_name)

    assert history_name in prompt
    assert "{search_history_tool_name}" not in prompt
    if history_name != "search_history":
        assert "search_history" not in prompt
