"""
vault.py — end-to-end encryption layer for VaultCLI.

Vault payload formats (stored in Supabase)
------------------------------------------
v1 (PBKDF2 / legacy)  : <hex_salt>$<fernet_token>
v2 (Argon2id / current): argon2$<hex_salt>$<fernet_token>

When a v1 vault is unlocked it is immediately re-saved as v2 on the next
write, completing the transparent migration.  The PBKDF2 code path is
therefore "read-only" from the user's perspective.
"""

import json
import os
import base64
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes

from vaultcli.core.config import CONFIG_DIR
from vaultcli.api.supabase_db import get_db
from vaultcli.core.session import (
    clear_master_unlock,
    load_master_unlock,
    load_session,
    save_master_unlock,
)
from vaultcli.crypto.key_derivation import (
    derive_fernet_key,
    derive_fernet_key_pbkdf2,
)

# ── Format tag used in the stored payload ──────────────────────────────────
_ARGON2_TAG = "argon2"

# ── in-memory session state (never written to disk) ───────────────────────
_session_key:  bytes | None = None
_session_salt: bytes | None = None


# ── internal helpers ──────────────────────────────────────────────────────

def _fernet() -> Fernet:
    if _session_key is None:
        raise RuntimeError("Master password has not been set for this session.")
    return Fernet(_session_key)


def _cache_cipher(user_id: str, refresh_token: str) -> Fernet:
    """Derive a short-lived cipher from non-secret session metadata."""
    material = f"{user_id}:{refresh_token}".encode()
    digest = hashes.Hash(hashes.SHA256())
    digest.update(material)
    return Fernet(base64.urlsafe_b64encode(digest.finalize()))


def _save_master_unlock_cache(user_id: str):
    if _session_key is None or _session_salt is None:
        return

    session = load_session()
    if not session:
        return

    refresh_token = session.get("refresh_token")
    if not refresh_token:
        return

    encrypted_key = _cache_cipher(user_id, refresh_token).encrypt(_session_key).decode()
    save_master_unlock(user_id, encrypted_key, _session_salt.hex())


# ── public state queries ───────────────────────────────────────────────────

def is_master_key_unlocked() -> bool:
    return _session_key is not None and _session_salt is not None


def try_restore_master_key(user_id: str) -> bool:
    global _session_key, _session_salt

    if is_master_key_unlocked():
        return True

    session = load_session()
    if not session:
        return False

    refresh_token = session.get("refresh_token")
    if not refresh_token:
        return False

    cached = load_master_unlock(user_id)
    if not cached:
        return False

    try:
        _session_key  = _cache_cipher(user_id, refresh_token).decrypt(
            cached["encrypted_key"].encode()
        )
        _session_salt = bytes.fromhex(cached["salt_hex"])
        return True
    except Exception:
        _session_key  = None
        _session_salt = None
        clear_master_unlock()
        return False


def clear_master_key():
    global _session_key, _session_salt
    _session_key  = None
    _session_salt = None
    clear_master_unlock()


# ── public API ────────────────────────────────────────────────────────────

def setup_master_password(user_id: str, master_password: str) -> bool:
    """
    Called once after login.  Derives and caches the session encryption key.

    Vault format detection
    ----------------------
    - No vault yet       → generate a fresh salt, derive Argon2id key, return False.
    - v2 (argon2$…)      → derive Argon2id key, verify, cache, return True.
    - v1 (<hex>$<tok>)   → derive legacy PBKDF2 key, verify, then immediately
                           regenerate with Argon2id so the next save upgrades
                           the format.  Returns True.
    - Legacy random key  → call _migrate_legacy() as before.

    Raises ValueError on wrong master password.
    """
    global _session_key, _session_salt

    raw = get_db().get_encrypted_vault(user_id)

    # ── No vault yet: create with Argon2id ───────────────────────────────
    if not raw:
        _session_salt = os.urandom(16)
        _session_key  = derive_fernet_key(master_password, _session_salt)
        _save_master_unlock_cache(user_id)
        return False

    # ── v2: argon2$<hex_salt>$<fernet_token> ─────────────────────────────
    if raw.startswith(f"{_ARGON2_TAG}$"):
        parts = raw.split("$", 2)
        if len(parts) != 3:
            raise ValueError("Corrupted vault payload (argon2 format).")
        _, hex_salt, token = parts
        salt          = bytes.fromhex(hex_salt)
        candidate_key = derive_fernet_key(master_password, salt)

        try:
            Fernet(candidate_key).decrypt(token.encode())
        except InvalidToken:
            raise ValueError("Wrong master password.")

        _session_salt = salt
        _session_key  = candidate_key
        _save_master_unlock_cache(user_id)
        return True

    # ── v1: <hex_salt>$<fernet_token>  (legacy PBKDF2) ───────────────────
    if "$" in raw:
        hex_salt, token = raw.split("$", 1)
        salt          = bytes.fromhex(hex_salt)
        candidate_key = derive_fernet_key_pbkdf2(master_password, salt)

        try:
            decrypted_payload = Fernet(candidate_key).decrypt(token.encode())
        except InvalidToken:
            raise ValueError("Wrong master password.")

        print("Upgrading vault encryption from PBKDF2 to Argon2id…")

        # Derive fresh Argon2id key (new salt for extra security)
        new_salt      = os.urandom(16)
        new_key       = derive_fernet_key(master_password, new_salt)
        new_token     = Fernet(new_key).encrypt(decrypted_payload).decode()
        new_payload   = f"{_ARGON2_TAG}${new_salt.hex()}${new_token}"

        get_db().save_encrypted_vault(user_id, new_payload)

        _session_salt = new_salt
        _session_key  = new_key
        _save_master_unlock_cache(user_id)
        print("Vault re-encrypted with Argon2id. Done.\n")
        return True

    # ── Very old format: random .vault_key file or plaintext ─────────────
    _migrate_legacy(user_id, raw, master_password)
    return True


def _migrate_legacy(user_id: str, raw: str, master_password: str):
    """Migrate from old random .vault_key approach to Argon2id encryption."""
    global _session_key, _session_salt

    OLD_KEY_FILE = os.path.join(CONFIG_DIR, ".vault_key")
    print("Migrating vault to Argon2id master-password encryption…")

    old_vault: dict = {}

    if os.path.exists(OLD_KEY_FILE):
        try:
            with open(OLD_KEY_FILE, "rb") as f:
                old_key = f.read().strip()
            old_vault = json.loads(Fernet(old_key).decrypt(raw.encode()))
            print("   Old vault decrypted via .vault_key")
        except Exception:
            print("   Could not decrypt with .vault_key — starting fresh.")
    else:
        # Very old plaintext format
        try:
            old_vault = json.loads(raw)
            print("   Old plaintext vault read.")
        except Exception:
            print("   Could not read old vault — starting fresh.")

    # Derive fresh Argon2id key and re-encrypt
    _session_salt = os.urandom(16)
    _session_key  = derive_fernet_key(master_password, _session_salt)
    save_vault(user_id, old_vault)
    _save_master_unlock_cache(user_id)

    if os.path.exists(OLD_KEY_FILE):
        os.remove(OLD_KEY_FILE)
        print(f"   Removed old key file: {OLD_KEY_FILE}")

    print("Migration complete. Your vault is now secured by Argon2id.\n")


def get_vault(user_id: str) -> dict:
    """Fetch and decrypt the vault for the given user."""
    raw = get_db().get_encrypted_vault(user_id)
    if not raw:
        return {}

    # v2: argon2$<hex_salt>$<fernet_token>
    if raw.startswith(f"{_ARGON2_TAG}$"):
        parts = raw.split("$", 2)
        if len(parts) != 3:
            return {}
        _, _, token = parts
    # v1 fallback (should only happen in the brief window between
    # setup_master_password detecting PBKDF2 and the first save completing)
    elif "$" in raw:
        _, token = raw.split("$", 1)
    else:
        return {}

    try:
        return json.loads(_fernet().decrypt(token.encode()))
    except InvalidToken:
        print("Decryption failed — check your master password.")
        return {}


def save_vault(user_id: str, vault: dict):
    """Encrypt and upsert the vault using the current Argon2id session key."""
    if _session_salt is None or _session_key is None:
        raise RuntimeError("Master password not initialised.")

    token   = _fernet().encrypt(json.dumps(vault).encode()).decode()
    payload = f"{_ARGON2_TAG}${_session_salt.hex()}${token}"

    get_db().save_encrypted_vault(user_id, payload)
