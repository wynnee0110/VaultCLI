from __future__ import annotations

import base64

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def derive_fernet_key(master_key: str, salt: bytes, *, iterations: int = 480_000) -> bytes:
    """Derive a Fernet-compatible key from a master key and random salt."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    )
    return base64.urlsafe_b64encode(kdf.derive(master_key.encode("utf-8")))
