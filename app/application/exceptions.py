class ApplicationError(Exception):
    code = "application_error"
    public_message = "Não foi possível concluir a operação."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.public_message)


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
