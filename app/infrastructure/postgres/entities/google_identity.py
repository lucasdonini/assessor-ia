from uuid import UUID

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class GoogleIdentityORM(Base):
    __tablename__ = "google_identities"

    subject: Mapped[str] = mapped_column(String(255), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), unique=True)


class GoogleGrantORM(Base):
    __tablename__ = "google_calendar_grants"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    email: Mapped[str] = mapped_column(String(320))
    ciphertext: Mapped[str] = mapped_column(Text)
