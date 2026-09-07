from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.model.transaction import Category, Transaction, TransactionType


class TransactionInput(BaseModel):
    amount: float = Field(..., description="Valor da transação (use positivo).")
    category: Category = Field(
        default=Category.OTHER,
        description=f"Nome da categoria: {' | '.join(Category)}",
    )
    transaction_type: TransactionType = Field(
        default=TransactionType.EXPENSE,
        description=f"Tipo da transação: {' | '.join(TransactionType)}",
    )
    description: Optional[str] = Field(
        default=None, description="Descrição (opcional)."
    )
    payment_method: Optional[str] = Field(
        default=None, description="Forma de pagamento (opcional)."
    )
    occurred_at: Optional[datetime] = Field(
        default=None,
        description=(
            "Data da transação segundo o prompt do usuário; "
            "se ausente, usa NOW() no banco."
        ),
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        description=(
            "Data da última modificação do registro. "
            "Preencha somente se houver um motivo claro para usar um valor diferente "
            "da data real de modificação no banco."
        ),
    )
    source_text: str = Field(..., description="Texto original do usuário.")
    is_canceled: bool = Field(
        default=False,
        description=(
            "Indica se a transação foi cancelada para o usuário ou não. "
            "Equivalente a excluir a transação se verdadeiro."
        ),
    )

    def to_domain(self, *, user_id: UUID) -> Transaction:
        return Transaction(user_id=user_id, **self.model_dump())


class TransactionOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    amount: float
    category: Category
    transaction_type: TransactionType
    description: Optional[str]
    payment_method: Optional[str]
    occurred_at: Optional[datetime]
    updated_at: Optional[datetime]
    source_text: str
    is_canceled: bool

    @classmethod
    def from_domain(cls, transaction: Transaction) -> "TransactionOutput":
        return cls(
            amount=transaction.amount,
            category=transaction.category,
            transaction_type=transaction.transaction_type,
            description=transaction.description,
            payment_method=transaction.payment_method,
            occurred_at=transaction.occurred_at,
            updated_at=transaction.updated_at,
            source_text=transaction.source_text,
            is_canceled=transaction.is_canceled,
        )
