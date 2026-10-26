from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, SecretStr


class GoogleIdentity(BaseModel):
    subject: str
    email: str


class GoogleTokens(BaseModel):
    access_token: SecretStr
    refresh_token: SecretStr | None = None
    expires_at: datetime


class OAuthTransaction(BaseModel):
    nonce: str
    verifier: SecretStr
    purpose: Literal["login", "calendar"]
    user_id: UUID | None = None
    session_hash: str | None = None


class WebSession(BaseModel):
    user_id: UUID
    subject: str
    email: str
    csrf: str


class CalendarConnection(BaseModel):
    connected: bool
    email: str | None = None
    reconnect_required: bool = False
