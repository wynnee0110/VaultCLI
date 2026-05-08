from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# Argon2id provides memory-hard password hashing suitable for login credentials.
_HASHER = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash plaintext password with Argon2id."""
    return _HASHER.hash(password)


def verify_password(password_hash: str, candidate_password: str) -> bool:
    """Verify candidate password against an Argon2id hash."""
    try:
        return _HASHER.verify(password_hash, candidate_password)
    except VerifyMismatchError:
        return False
