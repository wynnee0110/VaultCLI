"""
Secret type definitions and field schemas for VaultCli.

Supported secret types:
  - login        : username, email, password
  - api_key      : key name, api_key value
  - secure_note  : title, note body
  - ssh_key      : key name, private_key, public_key (optional), passphrase (optional)
"""

from __future__ import annotations

# Canonical type identifiers
TYPE_LOGIN       = "login"
TYPE_API_KEY     = "api_key"
TYPE_SECURE_NOTE = "secure_note"
TYPE_SSH_KEY     = "ssh_key"

ALL_TYPES = [TYPE_LOGIN, TYPE_API_KEY, TYPE_SECURE_NOTE, TYPE_SSH_KEY]

# Human-readable display labels
TYPE_LABELS: dict[str, str] = {
    TYPE_LOGIN:       "Account Login",
    TYPE_API_KEY:     "API Key",
    TYPE_SECURE_NOTE: "Secure Note / Plain Text",
    TYPE_SSH_KEY:     "SSH Key",
}

# Required fields for each type (used for validation)
REQUIRED_FIELDS: dict[str, list[str]] = {
    TYPE_LOGIN:       ["username"],
    TYPE_API_KEY:     ["key_name", "api_key"],
    TYPE_SECURE_NOTE: ["title", "note"],
    TYPE_SSH_KEY:     ["key_name", "private_key"],
}

# All known fields per type (for display ordering)
ALL_FIELDS: dict[str, list[str]] = {
    TYPE_LOGIN:       ["username", "email", "password"],
    TYPE_API_KEY:     ["key_name", "api_key"],
    TYPE_SECURE_NOTE: ["title", "note"],
    TYPE_SSH_KEY:     ["key_name", "private_key", "public_key", "passphrase"],
}

# Human-readable field labels (used in prompts and display)
FIELD_LABELS: dict[str, str] = {
    "username":    "Username",
    "email":       "Email",
    "password":    "Password",
    "key_name":    "Key Name",
    "api_key":     "API Key",
    "title":       "Title",
    "note":        "Note",
    "private_key": "Private Key",
    "public_key":  "Public Key",
    "passphrase":  "Passphrase",
}

# Fields that should be masked / treated as sensitive
SENSITIVE_FIELDS: set[str] = {"password", "api_key", "private_key", "passphrase"}

# Fields that are multi-line (note, private key, public key)
MULTILINE_FIELDS: set[str] = {"note", "private_key", "public_key"}


def get_type_label(secret_type: str) -> str:
    """Return human-readable label for a type identifier."""
    return TYPE_LABELS.get(secret_type, secret_type)


def get_display_summary(entry: dict) -> str:
    """
    Return a short one-line summary of an entry suitable for list display.
    Falls back gracefully if fields are missing.
    """
    t = entry.get("secret_type", TYPE_LOGIN)

    if t == TYPE_LOGIN:
        user  = entry.get("username", "-")
        email = entry.get("email", "")
        return f"{user}  {email}".strip()

    if t == TYPE_API_KEY:
        return entry.get("key_name", "-")

    if t == TYPE_SECURE_NOTE:
        return entry.get("title", "-")

    if t == TYPE_SSH_KEY:
        return entry.get("key_name", "-")

    return entry.get("key_name", entry.get("username", entry.get("title", "-")))
