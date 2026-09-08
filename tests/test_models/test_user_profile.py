from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.model.user_profile import RiskTolerance, UserProfile


@pytest.mark.parametrize("revenue", ["0", "-1", "NaN", "Infinity"])
def test_profile_rejects_invalid_revenue(revenue: str) -> None:
    with pytest.raises(ValueError):
        UserProfile(uuid4(), Decimal(revenue), "Travel", RiskTolerance.LOW, "Safe")


def test_profile_keeps_decimal_precision() -> None:
    profile = UserProfile(
        uuid4(), Decimal("4200.01"), "Travel", RiskTolerance.LOW, "Safe"
    )
    assert profile.monthly_revenue == Decimal("4200.01")
