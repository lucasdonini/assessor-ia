from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from uuid import UUID


class RiskTolerance(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass(frozen=True, slots=True)
class UserProfile:
    user_id: UUID
    monthly_revenue: Decimal
    objective: str
    risk_tolerance: RiskTolerance
    preferences: str

    def __post_init__(self) -> None:
        if not self.monthly_revenue.is_finite() or self.monthly_revenue <= 0:
            raise ValueError("Monthly revenue must be finite and positive")
        if not self.objective or len(self.objective) > 120:
            raise ValueError("Objective must contain between 1 and 120 characters")
        if not self.preferences:
            raise ValueError("Preferences cannot be blank")
