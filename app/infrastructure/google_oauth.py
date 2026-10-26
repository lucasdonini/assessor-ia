import base64
import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet
from google.auth import jwt
from pydantic import SecretStr

from app.application.models.google_identity import (
    GoogleIdentity,
    GoogleTokens,
    OAuthTransaction,
)
from app.infrastructure.config import GoogleConfig


class FernetTokenCipher:
    def __init__(self, config: GoogleConfig) -> None:
        self._config = config

    def _cipher(self) -> Fernet:
        if not self._config.encryption_key:
            raise ValueError("Calendar token encryption key is not configured")
        return Fernet(self._config.encryption_key.encode())

    def encrypt(self, tokens: GoogleTokens) -> str:
        raw = tokens.model_dump(mode="json")
        raw["access_token"] = tokens.access_token.get_secret_value()
        raw["refresh_token"] = (
            tokens.refresh_token.get_secret_value() if tokens.refresh_token else None
        )
        import json

        return (
            self._config.key_id
            + ":"
            + self._cipher().encrypt(json.dumps(raw).encode()).decode()
        )

    def decrypt(self, ciphertext: str) -> GoogleTokens:
        key_id, token = ciphertext.split(":", 1)
        if key_id != self._config.key_id:
            raise ValueError("Unknown token encryption key")
        return GoogleTokens.model_validate_json(self._cipher().decrypt(token.encode()))


class GoogleOAuthAdapter:
    def __init__(self, config: GoogleConfig) -> None:
        self._config = config

    def _client(self, purpose: str) -> tuple[str, str, str]:
        config = self._config
        if purpose == "calendar":
            return (
                config.calendar_client_id or config.client_id,
                config.calendar_client_secret or config.client_secret,
                config.calendar_redirect_uri,
            )
        return config.client_id, config.client_secret, config.login_redirect_uri

    def authorization_url(self, state: str, transaction: OAuthTransaction) -> str:
        client_id, _, redirect = self._client(transaction.purpose)
        if not client_id:
            raise ValueError("Google OAuth is not configured")
        challenge = (
            base64.urlsafe_b64encode(
                hashlib.sha256(
                    transaction.verifier.get_secret_value().encode()
                ).digest()
            )
            .rstrip(b"=")
            .decode()
        )
        params = {
            "client_id": client_id,
            "redirect_uri": redirect,
            "response_type": "code",
            "scope": "openid email",
            "state": state,
            "nonce": transaction.nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "prompt": "select_account",
        }
        if transaction.purpose == "calendar":
            params.update(
                scope="openid email https://www.googleapis.com/auth/calendar.events",
                access_type="offline",
                prompt="consent",
            )
        return self._config.authorization_url + "?" + urlencode(params)

    async def exchange(
        self, code: str, transaction: OAuthTransaction
    ) -> tuple[GoogleIdentity, GoogleTokens]:
        client_id, secret, redirect = self._client(transaction.purpose)
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                self._config.token_url,
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": secret,
                    "redirect_uri": redirect,
                    "grant_type": "authorization_code",
                    "code_verifier": transaction.verifier.get_secret_value(),
                },
            )
            response.raise_for_status()
            data = response.json()
            certs = await client.get(self._config.certs_url)
            certs.raise_for_status()
        identity = verify_google_identity(
            data["id_token"], certs.json(), client_id, transaction.nonce
        )
        if transaction.purpose == "calendar":
            scopes = set(data.get("scope", "").split())
            if "https://www.googleapis.com/auth/calendar.events" not in scopes:
                raise ValueError("Calendar write permission was not granted")
        return (
            identity,
            self._tokens(data),
        )

    def _tokens(self, data: dict[str, Any]) -> GoogleTokens:
        return GoogleTokens(
            access_token=SecretStr(data["access_token"]),
            refresh_token=(
                SecretStr(data["refresh_token"]) if data.get("refresh_token") else None
            ),
            expires_at=datetime.now(UTC) + timedelta(seconds=int(data["expires_in"])),
        )

    async def refresh(self, refresh_token: str) -> GoogleTokens:
        client_id, secret, _ = self._client("calendar")
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                self._config.token_url,
                data={
                    "client_id": client_id,
                    "client_secret": secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            response.raise_for_status()
        tokens = self._tokens(response.json())
        tokens.refresh_token = tokens.refresh_token or SecretStr(refresh_token)
        return tokens

    async def revoke(self, token: str) -> None:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(self._config.revoke_url, data={"token": token})
            response.raise_for_status()


def verify_google_identity(
    encoded: str, certs: dict[str, str], client_id: str, nonce: str
) -> GoogleIdentity:
    claims = cast(
        dict[str, Any],
        jwt.decode(encoded, certs=certs, audience=client_id),
    )
    if (
        claims.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}
        or claims.get("nonce") != nonce
        or claims.get("email_verified") is not True
        or claims.get("azp", client_id) != client_id
        or not claims.get("sub")
    ):
        raise ValueError("Invalid Google identity")
    return GoogleIdentity(subject=claims["sub"], email=claims["email"])
