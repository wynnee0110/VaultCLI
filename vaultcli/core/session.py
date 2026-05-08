import json
import os
from datetime import datetime, timedelta, timezone

from .config import SESSION_FILE, ensure_private_file, secure_write_json

MASTER_UNLOCK_TTL_SECONDS = 15 * 60


def _read_session_file() -> dict:
    try:
        ensure_private_file(SESSION_FILE)
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_session_file(data: dict):
    secure_write_json(SESSION_FILE, data)


def save_session(session):
    current = _read_session_file()
    current_user = ((current.get("user") or {}).get("id")) if current else None
    payload = {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "user": {
            "id": session.user.id
        }
    }

    # Keep a still-valid master unlock cache when auth tokens rotate.
    if current.get("master_unlock") and current_user == session.user.id:
        payload["master_unlock"] = current["master_unlock"]

    _write_session_file(payload)


def load_session():
    data = _read_session_file()
    if not data or not data.get("user"):
        return None
    return data


def save_master_unlock(user_id: str, encrypted_key: str, salt_hex: str):
    data = _read_session_file()
    if not data.get("user"):
        return

    data["master_unlock"] = {
        "user_id": user_id,
        "encrypted_key": encrypted_key,
        "salt_hex": salt_hex,
        "expires_at": (
            datetime.now(timezone.utc) + timedelta(seconds=MASTER_UNLOCK_TTL_SECONDS)
        ).isoformat(),
    }
    _write_session_file(data)


def load_master_unlock(user_id: str) -> dict | None:
    data = _read_session_file()
    cached = data.get("master_unlock")
    if not cached or cached.get("user_id") != user_id:
        return None

    expires_at = cached.get("expires_at")
    if not expires_at:
        return None

    try:
        expiry = datetime.fromisoformat(expires_at)
    except ValueError:
        clear_master_unlock()
        return None

    if expiry <= datetime.now(timezone.utc):
        clear_master_unlock()
        return None

    return cached


def clear_master_unlock():
    data = _read_session_file()
    if not data.get("master_unlock"):
        return

    data.pop("master_unlock", None)
    if data:
        _write_session_file(data)
        return

    clear_session()


def clear_session():
    """Delete the session file on logout."""
    try:
        os.remove(SESSION_FILE)
    except FileNotFoundError:
        pass
