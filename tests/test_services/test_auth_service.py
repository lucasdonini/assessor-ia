import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from app.application.models.google_identity import (
    GoogleIdentity,
    GoogleTokens,
    WebSession,
)
from app.infrastructure.config import GoogleConfig
from app.infrastructure.google_oauth import FernetTokenCipher
from app.services.auth_service import AuthenticationError, AuthService, token_hash


@pytest.fixture
def auth():
    repository = AsyncMock()
    state = AsyncMock()
    oauth = AsyncMock()
    oauth.authorization_url = lambda state, transaction: "https://accounts.google.com/"
    cipher = FernetTokenCipher(
        GoogleConfig(encryption_key=Fernet.generate_key().decode())
    )
    service = AuthService(repository, state, oauth, cipher)
    return service, repository, state, oauth, cipher


def tokens(expired=False):
    return GoogleTokens(
        access_token=SecretStr("private-access"),
        refresh_token=SecretStr("private-refresh"),
        expires_at=datetime.now(UTC) + timedelta(seconds=-1 if expired else 3600),
    )


def session():
    return WebSession(
        user_id=uuid4(),
        subject="verified-subject",
        email="test@example.com",
        csrf="csrf",
    )


def test_cipher_roundtrip_and_tampering(auth):
    cipher = auth[-1]
    encrypted = cipher.encrypt(tokens())
    assert "private-access" not in encrypted
    assert cipher.decrypt(encrypted).access_token.get_secret_value() == "private-access"
    with pytest.raises(Exception):
        cipher.decrypt(encrypted[:-4] + "aaaa")


@pytest.mark.asyncio
async def test_login_uses_subject_and_rotates_session(auth):
    service, repository, state, oauth, _ = auth
    _, browser_state = await service.begin("login")
    transaction = state.put_oauth.call_args.args[1]
    state.pop_oauth.return_value = transaction
    oauth.exchange.return_value = (
        GoogleIdentity(subject="stable-sub", email="test@example.com"),
        tokens(),
    )
    repository.resolve_identity.return_value = uuid4()
    new_token = await service.callback(
        "login", "code", browser_state, browser_state, "old-token"
    )
    repository.resolve_identity.assert_awaited_once_with("stable-sub")
    state.delete_session.assert_awaited_once_with(token_hash("old-token"))
    assert new_token and new_token != "old-token"
    assert state.put_session.call_args.args[0] == token_hash(new_token)


@pytest.mark.asyncio
async def test_callback_rejects_wrong_state_before_exchange(auth):
    service, _, state, oauth, _ = auth
    with pytest.raises(AuthenticationError):
        await service.callback("login", "code", "a", "b", None)
    state.pop_oauth.assert_not_awaited()
    oauth.exchange.assert_not_awaited()


@pytest.mark.asyncio
async def test_callback_rejects_replay(auth):
    service, _, state, oauth, _ = auth
    state.pop_oauth.return_value = None
    with pytest.raises(AuthenticationError):
        await service.callback("login", "code", "a", "a", None)
    oauth.exchange.assert_not_awaited()


@pytest.mark.asyncio
async def test_calendar_rejects_different_google_account(auth):
    service, repository, state, oauth, _ = auth
    state.get_session.return_value = session()
    _, browser_state = await service.begin("calendar", "cookie")
    state.pop_oauth.return_value = state.put_oauth.call_args.args[1]
    oauth.exchange.return_value = (
        GoogleIdentity(subject="another-sub", email="other@example.com"),
        tokens(),
    )
    with pytest.raises(AuthenticationError):
        await service.callback(
            "calendar", "code", browser_state, browser_state, "cookie"
        )
    repository.save_grant.assert_not_awaited()


@pytest.mark.asyncio
async def test_calendar_rejects_changed_session(auth):
    service, repository, state, oauth, _ = auth
    state.get_session.return_value = session()
    _, browser_state = await service.begin("calendar", "cookie")
    state.pop_oauth.return_value = state.put_oauth.call_args.args[1]
    with pytest.raises(AuthenticationError):
        await service.callback(
            "calendar", "code", browser_state, browser_state, "other-cookie"
        )
    oauth.exchange.assert_not_awaited()
    repository.save_grant.assert_not_awaited()


@pytest.mark.asyncio
async def test_disconnect_deletes_even_if_revoke_fails(auth):
    service, repository, _, oauth, cipher = auth
    owner = uuid4()
    repository.get_grant.return_value = ("a@example.com", cipher.encrypt(tokens()))
    oauth.revoke.side_effect = RuntimeError("private error")
    assert await service.disconnect(owner) is False
    repository.delete_grant.assert_awaited_once_with(owner)


@pytest.mark.asyncio
async def test_refresh_serializes_with_disconnect(auth):
    service, repository, _, oauth, cipher = auth
    owner = uuid4()
    repository.get_grant.return_value = ("a@example.com", cipher.encrypt(tokens(True)))
    oauth.refresh.return_value = tokens()
    async with service.calendar_access(owner) as token:
        assert token == "private-access"
        disconnect = asyncio.create_task(service.disconnect(owner))
        await asyncio.sleep(0)
        repository.delete_grant.assert_not_awaited()
    await disconnect
    oauth.refresh.assert_awaited_once_with("private-refresh")
    repository.save_grant.assert_awaited_once()
    repository.delete_grant.assert_awaited_once_with(owner)


@pytest.mark.asyncio
async def test_missing_session_and_absent_calendar(auth):
    service, repository, state, _, _ = auth
    state.get_session.return_value = None
    with pytest.raises(AuthenticationError):
        await service.session("unknown")
    repository.get_grant.return_value = None
    assert await service.access_token(uuid4()) is None
