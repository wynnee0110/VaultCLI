import json
import os
import base64
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

from vaultcli.core.config import CONFIG_DIR
from vaultcli.api.supabase_db import get_db
from vaultcli.core.session import clear_master_unlock, load_master_unlock, load_session, save_master_unlock

# OWASP 2023 recommended iteration count for PBKDF2-SHA256
ITERATIONS = 480_000

# ── in-memory session state (never written to disk) ──────────────
_session_key: bytes | None = None
_session_salt: bytes | None = None


# ── key derivation ───────────────────────────────────────────────

def _derive_key(password: str, salt: bytes) -> bytes:
    """Derive a 32-byte Fernet-compatible key via PBKDF2-HMAC-SHA256."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=ITERATIONS,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))


def _fernet() -> Fernet:
    if _session_key is None:
        raise RuntimeError("Master password has not been set for this session.")
    return Fernet(_session_key)


def _cache_cipher(user_id: str, refresh_token: str) -> Fernet:
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
        _session_key = _cache_cipher(user_id, refresh_token).decrypt(
            cached["encrypted_key"].encode()
        )
        _session_salt = bytes.fromhex(cached["salt_hex"])
        return True
    except Exception:
        _session_key = None
        _session_salt = None
        clear_master_unlock()
        return False


def clear_master_key():
    global _session_key, _session_salt
    _session_key = None
    _session_salt = None
    clear_master_unlock()


# ── public API ───────────────────────────────────────────────────

def setup_master_password(user_id: str, master_password: str) -> bool:
    """
    Called once after login. Derives and caches the session encryption key.

    - Existing vault  → reads salt from Supabase, derives key, verifies by
                        attempting a decryption. Raises ValueError on wrong password.
    - Legacy vault    → migrates from old random .vault_key file automatically.
    - New vault       → generates a fresh random salt, caches key, returns False.

    Returns True if an existing vault was unlocked, False if this is a new vault.
    """
    global _session_key, _session_salt

    raw = get_db().get_encrypted_vault(user_id)

    if not raw:
        # ── New user: generate fresh salt ─────────────────────────
        _session_salt = os.urandom(16)
        _session_key  = _derive_key(master_password, _session_salt)
        _save_master_unlock_cache(user_id)
        return False

    if "$" in raw:
        # ── Current format: <hex_salt>$<fernet_token> ─────────────
        hex_salt, token = raw.split("$", 1)
        salt = bytes.fromhex(hex_salt)
        candidate_key = _derive_key(master_password, salt)

        try:
            Fernet(candidate_key).decrypt(token.encode())
        except InvalidToken:
            raise ValueError("Wrong master password.")

        _session_salt = salt
        _session_key  = candidate_key
        _save_master_unlock_cache(user_id)
        return True

    else:
        # ── Legacy format: migrate from old .vault_key file ───────
        _migrate_legacy(user_id, raw, master_password)
        return True


def _migrate_legacy(user_id: str, raw: str, master_password: str):
    """Migrate from the old random .vault_key approach to password-derived key."""
    global _session_key, _session_salt

    OLD_KEY_FILE = os.path.join(CONFIG_DIR, ".vault_key")
    print("Migrating vault to master-password encryption...")

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

    # Derive new key and re-encrypt
    _session_salt = os.urandom(16)
    _session_key  = _derive_key(master_password, _session_salt)
    save_vault(user_id, old_vault)
    _save_master_unlock_cache(user_id)

    # Clean up the old key file
    if os.path.exists(OLD_KEY_FILE):
        os.remove(OLD_KEY_FILE)
        print(f"   Removed old key file: {OLD_KEY_FILE}")

    print("Migration complete. Your vault is now secured by your master password.\n")


def get_vault(user_id: str) -> dict:
    """Fetch and decrypt the vault for the given user."""
    raw = get_db().get_encrypted_vault(user_id)
    if not raw or "$" not in raw:
        return {}

    _, token = raw.split("$", 1)
    try:
        return json.loads(_fernet().decrypt(token.encode()))
    except InvalidToken:
        print("Decryption failed — check your master password.")
        return {}


def save_vault(user_id: str, vault: dict):
    """Encrypt and upsert the vault. Salt is stored as a hex prefix."""
    if _session_salt is None or _session_key is None:
        raise RuntimeError("Master password not initialised.")

    token   = _fernet().encrypt(json.dumps(vault).encode()).decode()
    payload = f"{_session_salt.hex()}${token}"

    get_db().save_encrypted_vault(user_id, payload)
