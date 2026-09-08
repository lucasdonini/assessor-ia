from beanie import Document


class UserProfileDocument(Document):
    # The UUID string is MongoDB's unique primary key, shared by every upsert.
    id: str  # type: ignore[assignment]
    monthly_revenue: str
    objective: str
    risk_tolerance: str
    preferences: str

    class Settings:
        name = "user_profiles"
