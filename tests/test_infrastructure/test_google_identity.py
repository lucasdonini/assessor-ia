import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from google.auth import crypt, jwt

from app.infrastructure.google_oauth import verify_google_identity


@pytest.fixture(scope="module")
def identity_key():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public = (
        key.public_key()
        .public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        .decode()
    )
    return crypt.RSASigner.from_string(private, key_id="synthetic"), {
        "synthetic": public
    }


def claims():
    return {
        "iss": "https://accounts.google.com",
        "aud": "our-client",
        "sub": "stable-subject",
        "email": "synthetic@example.com",
        "email_verified": True,
        "nonce": "our-nonce",
        "iat": int(time.time()) - 10,
        "exp": int(time.time()) + 3600,
    }


def test_accepts_a_valid_signed_identity(identity_key):
    signer, certs = identity_key
    encoded = jwt.encode(signer, claims()).decode()
    assert (
        verify_google_identity(encoded, certs, "our-client", "our-nonce").subject
        == "stable-subject"
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"aud": "another-client"},
        {"nonce": "another-browser"},
        {"iss": "https://attacker.example"},
        {"email_verified": False},
        {"email_verified": "false"},
        {"exp": 1},
        {"azp": "another-client"},
    ],
)
def test_rejects_untrusted_identity_claims(identity_key, overrides):
    signer, certs = identity_key
    encoded = jwt.encode(signer, claims() | overrides).decode()
    with pytest.raises(ValueError):
        verify_google_identity(encoded, certs, "our-client", "our-nonce")


def test_rejects_invalid_signature(identity_key):
    signer, certs = identity_key
    encoded = jwt.encode(signer, claims()).decode()
    parts = encoded.split(".")
    parts[-1] = "a" * len(parts[-1])
    with pytest.raises(ValueError):
        verify_google_identity(".".join(parts), certs, "our-client", "our-nonce")
