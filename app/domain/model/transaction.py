from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID


class Category(str, Enum):
    FOOD = "comida"
    JUNK = "besteira"
    STUDIES = "estudo"
    VACATION = "férias"
    TRANSPORTATION = "transporte"
    HOUSING = "moradia"
    HEALTH = "saúde"
    LIESURE = "lazer"
    BILLS = "contas"
    INVESTMENT = "investimento"
    GIFTS = "presente"
    OTHER = "outros"


class TransactionType(str, Enum):
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"
    TRANSFER = "TRANSFER"


@dataclass(slots=True)
class Transaction:
    user_id: UUID
    amount: float
    source_text: str
    category: Category = Category.OTHER
    transaction_type: TransactionType = TransactionType.EXPENSE
    description: Optional[str] = None
    payment_method: Optional[str] = None
    occurred_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    is_canceled: bool = False
    id: Optional[UUID] = None
