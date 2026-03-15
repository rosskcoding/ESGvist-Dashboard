"""
Secret encryption helpers (symmetric, server-side).

Used for storing sensitive tenant settings such as per-company OpenAI API keys.

Design goals:
- Safe-by-default storage: DB never stores plaintext when encryption is configured.
- Backward compatible: can read legacy plaintext values (returns as-is).
- Stateless: encryption key derived from server configuration.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

ENC_PREFIX = "enc:"  # prefix to distinguish encrypted tokens from legacy plaintext


def _derive_fernet_key(secret: str) -> bytes:
    """
    Derive a Fernet key from an arbitrary secret string.

    Fernet requires a 32-byte urlsafe base64-encoded key.
    """
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _get_fernet() -> Fernet:
    """
    Get Fernet instance derived from configuration.

    Priority:
    1) OPENAI_KEY_ENCRYPTION_SECRET (if configured)
    2) SECRET_KEY (fallback)
    """
    if settings.openai_key_encryption_secret:
        raw = settings.openai_key_encryption_secret.get_secret_value()
    else:
        raw = settings.secret_key.get_secret_value()
    return Fernet(_derive_fernet_key(raw))


def encrypt_secret(plaintext: str) -> str:
    """Encrypt plaintext and return storage-safe string."""
    token = _get_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")
    return f"{ENC_PREFIX}{token}"


def decrypt_secret(value: str) -> str:
    """
    Decrypt stored value.

    - If value is prefixed with ENC_PREFIX → decrypt.
    - If value is legacy plaintext → return as-is.
    """
    if not value.startswith(ENC_PREFIX):
        return value

    token = value[len(ENC_PREFIX) :]
    try:
        return _get_fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        # Treat as corrupted/unknown; return as-is to avoid leaking errors upstream.
        # Callers should validate the key with OpenAI and mark it invalid if needed.
        return value



