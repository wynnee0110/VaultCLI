"""
Key derivation helpers for VaultCLI.

Current algorithm : Argon2id  (argon2-cffi ≥ 23.1.0)
Legacy algorithm  : PBKDF2-HMAC-SHA256  (cryptography ≥ 40)

The legacy path exists solely so that existing vaults encrypted with
PBKDF2 can still be unlocked and then transparently migrated to Argon2id
on the very next save.
"""
from __future__ import annotations

import base64

from argon2.low_level import Type, hash_secret_raw
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# ── Argon2id parameters (OWASP 2023 interactive-login recommendation) ──────
# m=64 MiB, t=3 passes, p=4 threads → ~0.5 s on modern hardware
ARGON2_TIME_COST   = 3
ARGON2_MEMORY_COST = 65_536   # KiB == 64 MiB
ARGON2_PARALLELISM = 4
ARGON2_HASH_LEN    = 32

# ── Legacy PBKDF2 parameters (kept only for reading old vaults) ─────────────
PBKDF2_ITERATIONS  = 480_000


def derive_fernet_key(master_password: str, salt: bytes) -> bytes:
    """
    Derive a 32-byte Fernet-compatible key using Argon2id.

    This is the **current** algorithm for all new and re-encrypted vaults.
    """
    raw = hash_secret_raw(
        secret=master_password.encode("utf-8"),
        salt=salt,
        time_cost=ARGON2_TIME_COST,
        memory_cost=ARGON2_MEMORY_COST,
        parallelism=ARGON2_PARALLELISM,
        hash_len=ARGON2_HASH_LEN,
        type=Type.ID,
    )
    return base64.urlsafe_b64encode(raw)


def derive_fernet_key_pbkdf2(master_password: str, salt: bytes) -> bytes:
    """
    Derive a Fernet-compatible key using legacy PBKDF2-HMAC-SHA256.

    Used **only** when reading vaults that were created before the Argon2
    upgrade, so that they can be unlocked and then re-saved under Argon2id.
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return base64.urlsafe_b64encode(kdf.derive(master_password.encode("utf-8")))
