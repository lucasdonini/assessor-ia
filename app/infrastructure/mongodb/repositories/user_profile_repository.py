from uuid import UUID

from app.domain.model.user_profile import UserProfile
from app.infrastructure.mongodb.entities.user_profile import UserProfileDocument
from app.infrastructure.mongodb.mappers.user_profile_mapper import UserProfileMapper


class BeanieUserProfileRepository:
    async def upsert(self, profile: UserProfile) -> None:
        document = UserProfileMapper.to_document(profile)
        await UserProfileDocument.get_pymongo_collection().replace_one(
            {"_id": str(profile.user_id)},
            document.model_dump(by_alias=True, exclude={"revision_id"}),
            upsert=True,
        )

    async def find_by_user_id(self, user_id: UUID) -> UserProfile | None:
        document = await UserProfileDocument.get(str(user_id))
        return UserProfileMapper.to_model(document) if document else None
