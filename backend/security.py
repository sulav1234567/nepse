"""
Central security primitives: JWT signing-key management and at-rest encryption
for sensitive third-party credentials (MeroShare / TMS broker logins).

Design goals
------------
* **Fail-closed in production.** The JWT secret and the credential-encryption key
  MUST come from the environment in production. We never fall back to a hardcoded
  key that an attacker could read from source and use to forge sessions.
* **Never store broker passwords in plaintext.** Broker credentials are encrypted
  with Fernet (AES-128-CBC + HMAC) using a dedicated key, so a database leak does
  not expose users' brokerage logins.
"""

from __future__ import annotations

import logging
import os
import secrets

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger("nepse-alpha.security")

# "production" / "prod" => strict, fail-closed. Anything else => dev conveniences.
APP_ENV = os.getenv("APP_ENV", os.getenv("ENV", "development")).lower()
IS_PRODUCTION = APP_ENV in {"production", "prod"}


# ─────────────────────────────────────────────────────────────────────────────
# JWT signing key
# ─────────────────────────────────────────────────────────────────────────────

def get_jwt_secret() -> str:
    """Return the JWT signing secret.

    In production a missing ``JWT_SECRET_KEY`` is a hard error (we refuse to boot
    with a guessable key). In development we generate a random ephemeral secret so
    local runs work — but tokens won't survive a restart, which is fine for dev.
    """
    secret = os.getenv("JWT_SECRET_KEY", "").strip()
    if secret:
        if len(secret) < 32:
            logger.warning("JWT_SECRET_KEY is shorter than 32 chars — use a longer random secret.")
        return secret

    if IS_PRODUCTION:
        raise RuntimeError(
            "JWT_SECRET_KEY is not set. Refusing to start in production with a "
            "hardcoded/guessable signing key. Generate one with: "
            "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )

    ephemeral = secrets.token_urlsafe(48)
    logger.warning(
        "JWT_SECRET_KEY not set — using a random EPHEMERAL secret for this dev run. "
        "Sessions will be invalidated on restart. Set JWT_SECRET_KEY for stable auth."
    )
    return ephemeral


# ─────────────────────────────────────────────────────────────────────────────
# Credential encryption (broker logins at rest)
# ─────────────────────────────────────────────────────────────────────────────

def _load_fernet() -> Fernet | None:
    """Build the Fernet cipher from ``CREDENTIAL_ENCRYPTION_KEY``.

    Returns ``None`` (rather than raising) when no key is configured, so the app
    boots; callers that actually try to store/read a credential get a clear error.
    """
    key = os.getenv("CREDENTIAL_ENCRYPTION_KEY", "").strip()
    if not key:
        return None
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as exc:  # malformed key
        logger.error("CREDENTIAL_ENCRYPTION_KEY is invalid (must be a urlsafe base64 32-byte Fernet key): %s", exc)
        if IS_PRODUCTION:
            raise
        return None


_fernet = _load_fernet()


def credential_encryption_available() -> bool:
    return _fernet is not None


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a sensitive string (e.g. a broker password) for storage at rest."""
    if _fernet is None:
        raise RuntimeError(
            "Credential encryption is not configured. Set CREDENTIAL_ENCRYPTION_KEY "
            "(generate with: python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\") before connecting a broker account."
        )
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt_secret(token: str) -> str:
    """Decrypt a value previously produced by :func:`encrypt_secret`."""
    if _fernet is None:
        raise RuntimeError("Credential encryption is not configured (CREDENTIAL_ENCRYPTION_KEY missing).")
    try:
        return _fernet.decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise RuntimeError("Failed to decrypt credential — the encryption key may have changed.") from exc


def generate_fernet_key() -> str:
    """Helper to mint a new credential-encryption key (for setup/docs)."""
    return Fernet.generate_key().decode()
