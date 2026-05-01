import json
import os
import base64
from auth import supabase
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

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

    res = (
        supabase.table("vaults")
        .select("encrypted_vault")
        .eq("user_id", user_id)
        .execute()
    )

    raw = (res.data[0].get("encrypted_vault") or "") if res.data else ""

    if not raw:
        # ── New user: generate fresh salt ─────────────────────────
        _session_salt = os.urandom(16)
        _session_key  = _derive_key(master_password, _session_salt)
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
        return True

    else:
        # ── Legacy format: migrate from old .vault_key file ───────
        _migrate_legacy(user_id, raw, master_password)
        return True


def _migrate_legacy(user_id: str, raw: str, master_password: str):
    """Migrate from the old random .vault_key approach to password-derived key."""
    global _session_key, _session_salt

    OLD_KEY_FILE = os.path.join(os.path.expanduser("~/.vaultcli"), ".vault_key")
    print("🔄 Migrating vault to master-password encryption...")

    old_vault: dict = {}

    if os.path.exists(OLD_KEY_FILE):
        try:
            with open(OLD_KEY_FILE, "rb") as f:
                old_key = f.read().strip()
            old_vault = json.loads(Fernet(old_key).decrypt(raw.encode()))
            print("   ✅ Old vault decrypted via .vault_key")
        except Exception:
            print("   ⚠️  Could not decrypt with .vault_key — starting fresh.")
    else:
        # Very old plaintext format
        try:
            old_vault = json.loads(raw)
            print("   ✅ Old plaintext vault read.")
        except Exception:
            print("   ⚠️  Could not read old vault — starting fresh.")

    # Derive new key and re-encrypt
    _session_salt = os.urandom(16)
    _session_key  = _derive_key(master_password, _session_salt)
    save_vault(user_id, old_vault)

    # Clean up the old key file
    if os.path.exists(OLD_KEY_FILE):
        os.remove(OLD_KEY_FILE)
        print(f"   🗑️  Removed old key file: {OLD_KEY_FILE}")

    print("✅ Migration complete. Your vault is now secured by your master password.\n")


def get_vault(user_id: str) -> dict:
    """Fetch and decrypt the vault for the given user."""
    res = (
        supabase.table("vaults")
        .select("encrypted_vault")
        .eq("user_id", user_id)
        .execute()
    )

    raw = (res.data[0].get("encrypted_vault") or "") if res.data else ""
    if not raw or "$" not in raw:
        return {}

    _, token = raw.split("$", 1)
    try:
        return json.loads(_fernet().decrypt(token.encode()))
    except InvalidToken:
        print("❌ Decryption failed — check your master password.")
        return {}


def save_vault(user_id: str, vault: dict):
    """Encrypt and upsert the vault. Salt is stored as a hex prefix."""
    if _session_salt is None or _session_key is None:
        raise RuntimeError("Master password not initialised.")

    token   = _fernet().encrypt(json.dumps(vault).encode()).decode()
    payload = f"{_session_salt.hex()}${token}"

    supabase.table("vaults").upsert({
        "user_id":         user_id,
        "encrypted_vault": payload,
    }).execute()