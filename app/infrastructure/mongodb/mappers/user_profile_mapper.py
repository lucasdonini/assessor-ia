from decimal import Decimal
from uuid import UUID

from app.domain.model.user_profile import RiskTolerance, UserProfile
from app.infrastructure.mongodb.entities.user_profile import UserProfileDocument


class UserProfileMapper:
    @staticmethod
    def to_document(profile: UserProfile) -> UserProfileDocument:
        return UserProfileDocument(
            id=str(profile.user_id),
            monthly_revenue=str(profile.monthly_revenue),
            objective=profile.objective,
            risk_tolerance=profile.risk_tolerance.value,
            preferences=profile.preferences,
        )

    @staticmethod
    def to_model(document: UserProfileDocument) -> UserProfile:
        return UserProfile(
            user_id=UUID(document.id),
            monthly_revenue=Decimal(document.monthly_revenue),
            objective=document.objective,
            risk_tolerance=RiskTolerance(document.risk_tolerance),
            preferences=document.preferences,
        )
