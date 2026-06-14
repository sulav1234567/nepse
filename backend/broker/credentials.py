"""
Per-user broker credential storage (MeroShare / TMS), encrypted at rest.

Secret fields (password, PIN) are stored only as Fernet ciphertext via
backend.security; identifiers (DP, username, TMS url) are stored as-is so the UI
can show which account is linked. Nothing sensitive is ever persisted in plaintext.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from ..database import UserManager
from ..security import decrypt_secret, encrypt_secret

# Fields that must be encrypted before they touch the database.
_SECRET_FIELDS = {"password", "pin"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_credentials(user_id: str, provider: str, fields: dict[str, str]) -> None:
    """Encrypt secret fields and persist the credential blob under the user doc."""
    stored: dict[str, Any] = {"connected_at": _now()}
    for key, value in fields.items():
        if not value:
            continue
        if key in _SECRET_FIELDS:
            stored[f"{key}_enc"] = encrypt_secret(value)
        else:
            stored[key] = value
    UserManager.update_user(user_id, {f"broker_credentials.{provider}": stored})


def load_credentials(user_id: str, provider: str) -> Optional[dict[str, str]]:
    """Return decrypted credentials for use against the broker, or None."""
    user = UserManager.get_user_by_id(user_id)
    if not user:
        return None
    creds = (user.get("broker_credentials") or {}).get(provider)
    if not creds:
        return None
    out: dict[str, str] = {}
    for key, value in creds.items():
        if key == "connected_at":
            continue
        if key.endswith("_enc"):
            out[key[:-4]] = decrypt_secret(value)
        else:
            out[key] = value
    return out


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 3:
        return "•" * len(value)
    return value[:2] + "•" * (len(value) - 3) + value[-1]


def credential_status(user_id: str, provider: str) -> dict[str, Any]:
    """Non-sensitive connection status for the UI (never returns secrets)."""
    user = UserManager.get_user_by_id(user_id)
    creds = ((user or {}).get("broker_credentials") or {}).get(provider) if user else None
    if not creds:
        return {"connected": False, "provider": provider}
    public = {
        key: (_mask(str(value)) if key == "username" else value)
        for key, value in creds.items()
        if not key.endswith("_enc") and key != "connected_at"
    }
    return {"connected": True, "provider": provider, "connected_at": creds.get("connected_at"), **public}


def delete_credentials(user_id: str, provider: str) -> None:
    """Remove stored credentials for a provider (disconnect)."""
    UserManager.update_user(user_id, {f"broker_credentials.{provider}": None})
