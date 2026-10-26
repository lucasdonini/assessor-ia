from typing import Protocol

from app.application.models.google_identity import (
    GoogleIdentity,
    GoogleTokens,
    OAuthTransaction,
)


class GoogleOAuth(Protocol):
    def authorization_url(self, state: str, transaction: OAuthTransaction) -> str: ...

    async def exchange(
        self, code: str, transaction: OAuthTransaction
    ) -> tuple[GoogleIdentity, GoogleTokens]: ...

    async def refresh(self, refresh_token: str) -> GoogleTokens: ...

    async def revoke(self, token: str) -> None: ...


class TokenCipher(Protocol):
    def encrypt(self, tokens: GoogleTokens) -> str: ...

    def decrypt(self, ciphertext: str) -> GoogleTokens: ...
