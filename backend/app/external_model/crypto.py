from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


class CredentialCipherError(Exception):
    """Raised when credentials can't be encrypted/decrypted."""


class CredentialCipher:
    """Symmetric encryption-at-rest for per-user external credentials.

    Key is a urlsafe-base64 Fernet key from ``CREDENTIAL_ENCRYPTION_KEY``
    (generate with ``Fernet.generate_key()``).
    """

    def __init__(self, key: str) -> None:
        if not key:
            raise CredentialCipherError("CREDENTIAL_ENCRYPTION_KEY is not configured")
        try:
            self._fernet = Fernet(key.encode())
        except (ValueError, TypeError) as exc:
            raise CredentialCipherError(
                "CREDENTIAL_ENCRYPTION_KEY is not a valid Fernet key"
            ) from exc

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken as exc:
            raise CredentialCipherError("stored credential could not be decrypted") from exc


def mask_secret(secret: str) -> str:
    """A safe-to-display hint: first 3 + last 4, e.g. ``sk-…ab12``. Never the full value."""
    s = secret.strip()
    if not s:
        return ""
    if len(s) <= 8:
        return "…" + s[-2:]
    return f"{s[:3]}…{s[-4:]}"
