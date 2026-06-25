from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from app.external_model.crypto import CredentialCipher, CredentialCipherError, mask_secret


def _key() -> str:
    return Fernet.generate_key().decode()


def test_encrypt_decrypt_roundtrip() -> None:
    cipher = CredentialCipher(_key())
    enc = cipher.encrypt("sk-supersecret-123")
    assert enc != "sk-supersecret-123"  # actually encrypted
    assert cipher.decrypt(enc) == "sk-supersecret-123"


def test_decrypt_with_wrong_key_raises() -> None:
    a = CredentialCipher(_key())
    b = CredentialCipher(_key())
    with pytest.raises(CredentialCipherError):
        b.decrypt(a.encrypt("x"))


def test_empty_key_raises() -> None:
    with pytest.raises(CredentialCipherError):
        CredentialCipher("")


def test_invalid_key_raises() -> None:
    with pytest.raises(CredentialCipherError):
        CredentialCipher("not-a-valid-fernet-key")


def test_mask_secret() -> None:
    masked = mask_secret("sk-1234567890abcd")
    assert masked.startswith("sk-")
    assert masked.endswith("abcd")
    assert "…" in masked
    assert "1234567890" not in masked  # middle hidden
    assert mask_secret("") == ""
    assert mask_secret("short") == "…rt"  # short secrets reveal only last 2
