import asyncio
import hashlib
import secrets
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from pydantic import SecretStr

from app.application.models.google_identity import (
    CalendarConnection,
    OAuthTransaction,
    WebSession,
)
from app.application.ports.google_oauth import GoogleOAuth, TokenCipher
from app.application.repositories.auth_repository import (
    AuthRepository,
    AuthStateRepository,
)


class AuthenticationError(Exception):
    """Safe authentication rejection; provider details must not reach users."""


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class AuthService:
    def __init__(
        self,
        repository: AuthRepository,
        state: AuthStateRepository,
        oauth: GoogleOAuth,
        cipher: TokenCipher,
    ) -> None:
        self._repository = repository
        self._state = state
        self._oauth = oauth
        self._cipher = cipher
        self._locks: defaultdict[UUID, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def begin(
        self, purpose: Literal["login", "calendar"], session_token: str | None = None
    ) -> tuple[str, str]:
        session = await self.session(session_token) if purpose == "calendar" else None
        state = secrets.token_urlsafe(32)
        transaction = OAuthTransaction(
            nonce=secrets.token_urlsafe(32),
            verifier=SecretStr(secrets.token_urlsafe(64)),
            purpose=purpose,
            user_id=session.user_id if session else None,
            session_hash=token_hash(session_token)
            if session_token and session
            else None,
        )
        url = self._oauth.authorization_url(state, transaction)
        await self._state.put_oauth(token_hash(state), transaction)
        return url, state

    async def callback(
        self,
        purpose: Literal["login", "calendar"],
        code: str,
        state: str,
        browser_state: str,
        session_token: str | None,
    ) -> str | None:
        if not secrets.compare_digest(state, browser_state):
            raise AuthenticationError()
        transaction = await self._state.pop_oauth(token_hash(state))
        if transaction is None or transaction.purpose != purpose:
            raise AuthenticationError()
        session = None
        if purpose == "calendar":
            session = await self.session(session_token)
            if (
                transaction.user_id != session.user_id
                or transaction.session_hash != token_hash(session_token or "")
            ):
                raise AuthenticationError()
        identity, tokens = await self._oauth.exchange(code, transaction)
        if session:
            if identity.subject != session.subject:
                raise AuthenticationError()
            if not tokens.refresh_token:
                raise AuthenticationError()
            async with self._locks[session.user_id]:
                # A logout during consent invalidates the callback too.
                await self.session(session_token)
                await self._repository.save_grant(
                    session.user_id, identity.email, self._cipher.encrypt(tokens)
                )
            return None
        user_id = await self._repository.resolve_identity(identity.subject)
        await self.logout(session_token)
        new_token = secrets.token_urlsafe(32)
        await self._state.put_session(
            token_hash(new_token),
            WebSession(
                user_id=user_id,
                subject=identity.subject,
                email=identity.email,
                csrf=secrets.token_urlsafe(32),
            ),
        )
        return new_token

    async def session(self, token: str | None) -> WebSession:
        result = await self._state.get_session(token_hash(token)) if token else None
        if result is None:
            raise AuthenticationError()
        return result

    async def logout(self, token: str | None) -> None:
        if token:
            await self._state.delete_session(token_hash(token))

    async def connection(self, user_id: UUID) -> CalendarConnection:
        grant = await self._repository.get_grant(user_id)
        if not grant:
            return CalendarConnection(connected=False)
        try:
            tokens = self._cipher.decrypt(grant[1])
            reconnect = (
                tokens.expires_at <= datetime.now(UTC) and not tokens.refresh_token
            )
        except Exception:
            reconnect = True
        return CalendarConnection(
            connected=True, email=grant[0], reconnect_required=reconnect
        )

    async def access_token(self, user_id: UUID) -> str | None:
        async with self.calendar_access(user_id) as token:
            return token

    @asynccontextmanager
    async def calendar_access(self, user_id: UUID) -> AsyncIterator[str | None]:
        async with self._locks[user_id]:
            grant = await self._repository.get_grant(user_id)
            if not grant:
                yield None
                return
            tokens = self._cipher.decrypt(grant[1])
            if tokens.expires_at <= datetime.now(UTC) + timedelta(seconds=30):
                if not tokens.refresh_token:
                    raise AuthenticationError()
                tokens = await self._oauth.refresh(
                    tokens.refresh_token.get_secret_value()
                )
                await self._repository.save_grant(
                    user_id, grant[0], self._cipher.encrypt(tokens)
                )
            yield tokens.access_token.get_secret_value()

    async def disconnect(self, user_id: UUID) -> bool:
        async with self._locks[user_id]:
            grant = await self._repository.get_grant(user_id)
            await self._repository.delete_grant(user_id)
            if grant:
                try:
                    tokens = self._cipher.decrypt(grant[1])
                    await self._oauth.revoke(
                        (tokens.refresh_token or tokens.access_token).get_secret_value()
                    )
                except Exception:
                    return False
            return True
