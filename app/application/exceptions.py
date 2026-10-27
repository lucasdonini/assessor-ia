class ApplicationError(Exception):
    code = "application_error"
    public_message = "Não foi possível concluir a operação."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.public_message)


class UnsupportedCurrencyError(ApplicationError):
    code = "unsupported_currency"
    public_message = (
        "Informe um único valor explícito em reais (BRL). "
        "Não registro nem converto valores em outras moedas."
    )


class MixedCurrencyBalanceError(UnsupportedCurrencyError):
    code = "mixed_currency_balance"
    public_message = (
        "O saldo inclui registros em outras moedas. "
        "Não posso apresentar um total em BRL sem conversão."
    )


class EvidenceRejectedError(ApplicationError):
    code = "evidence_rejected"
    public_message = "Não tenho evidência para afirmar isso."


class FinancialOutcomeUnknownError(ApplicationError):
    code = "financial_outcome_unknown"
    public_message = (
        "Não foi possível confirmar o resultado da operação. "
        "Verifique os lançamentos antes de repetir."
    )


class SessionHistoryIndexError(ApplicationError):
    code = "session_history_index_error"
    public_message = "Não foi possível acessar a memória de conversas anteriores."


class ProfileUnavailableError(ApplicationError):
    code = "profile_unavailable"
    public_message = (
        "Não foi possível concluir a operação do perfil. "
        "Tente salvar novamente pela tela Perfil."
    )


class InvalidTransactionCommandError(ApplicationError):
    code = "invalid_transaction_command"
    public_message = "Os dados informados para a operação são inválidos."


class MissingTransactionReferenceError(InvalidTransactionCommandError):
    code = "missing_transaction_reference"
    public_message = (
        "Informe o ID da transação ou o texto e a data usados para localizá-la."
    )


class NoTransactionChangesError(InvalidTransactionCommandError):
    code = "no_transaction_changes"
    public_message = "Informe ao menos um campo para atualizar."


class TransactionNotFoundError(ApplicationError):
    code = "transaction_not_found"
    public_message = "A transação informada não foi encontrada."


class TransactionConflictError(ApplicationError):
    code = "transaction_conflict"
    public_message = "O estado atual da transação impede esta operação."


class AmbiguousTransactionError(TransactionConflictError):
    code = "ambiguous_transaction"
    public_message = (
        "Mais de uma transação corresponde à busca. Informe o ID da transação."
    )
