import uuid

from vaultcli.core.secret_types import (
    TYPE_LOGIN,
    TYPE_API_KEY,
    TYPE_SECURE_NOTE,
    TYPE_SSH_KEY,
    get_display_summary,
)


def migrate_vault(vault: dict) -> dict:
    """
    Migrate old vault formats to the current multi-type format.

    Supported migrations
    --------------------
    v0 → v1  : flat {"accounts": [...]} → {"services": {"App": [...]}}
    v1 → v2  : add `secret_type` field to every entry that lacks one
               (all legacy entries become TYPE_LOGIN)
    """
    # --- v0 → v1 ---------------------------------------------------------
    if "accounts" in vault and "services" not in vault:
        print("Migrating vault to service-grouped format...")
        services: dict = {}
        for acc in vault["accounts"]:
            app = acc.get("app", "Unknown")
            entry = {
                "id":          acc.get("id", str(uuid.uuid4())),
                "secret_type": TYPE_LOGIN,
                "username":    acc.get("username", ""),
                "email":       acc.get("email", ""),
                "password":    acc.get("password", ""),
            }
            services.setdefault(app, []).append(entry)
        vault = {"services": services}
        print("Migration complete.\n")

    elif "services" not in vault:
        vault = {"services": {}}

    # --- v1 → v2 : stamp secret_type on every entry that's missing it ----
    for accounts in vault["services"].values():
        for entry in accounts:
            if "secret_type" not in entry:
                entry["secret_type"] = TYPE_LOGIN

    return vault


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def parse_secret_path(path: str) -> tuple[str, str]:
    """
    Parse a shortcut path like ``<service>/<identifier>``.

    The identifier is type-specific:
      - login       : username  (or username/email as legacy 3-part path)
      - api_key     : key_name
      - secure_note : title
      - ssh_key     : key_name

    Returns (service_name, identifier).
    Raises ValueError on bad format.
    """
    parts = [p.strip() for p in path.split("/")]

    # legacy 3-part: service/username/email → still valid, collapse to 2-part
    if len(parts) == 3:
        service_name, username, email = parts
        if not service_name or (not username and not email):
            raise ValueError(
                "Path must look like <service>/<username> or <service>/<username>/<email>."
            )
        # Treat as login lookup by username only (email match is bonus)
        return service_name, username

    if len(parts) == 2:
        service_name, identifier = parts
        if not service_name or not identifier:
            raise ValueError("Path must look like <service>/<identifier>.")
        return service_name, identifier

    raise ValueError(
        "Path must look like <service>/<identifier> "
        "(e.g. github/myuser  or  aws/prod-key  or  notes/todo)."
    )


def find_entry_by_path(vault: dict, path: str) -> tuple[dict | None, str, str]:
    """
    Locate an entry by its shortcut path.

    Returns (entry_or_None, service_name, identifier).
    The identifier is matched against the type-specific primary field.
    """
    service_name, identifier = parse_secret_path(path)
    vault = migrate_vault(vault)
    accounts = vault["services"].get(service_name, [])

    def _primary(entry: dict) -> str:
        t = entry.get("secret_type", TYPE_LOGIN)
        if t == TYPE_LOGIN:
            return entry.get("username", "")
        if t == TYPE_API_KEY:
            return entry.get("key_name", "")
        if t == TYPE_SECURE_NOTE:
            return entry.get("title", "")
        if t == TYPE_SSH_KEY:
            return entry.get("key_name", "")
        return ""

    match = next((e for e in accounts if _primary(e) == identifier), None)
    return match, service_name, identifier


# Keep the old name as an alias so existing callers don't break immediately
def find_account_by_path(vault: dict, path: str) -> tuple[dict | None, str, str, str]:
    """Backward-compat wrapper around find_entry_by_path."""
    match, service_name, identifier = find_entry_by_path(vault, path)
    # Legacy callers expect a 4-tuple: (match, service, username, email)
    username = match.get("username", identifier) if match else identifier
    email    = match.get("email",    "")         if match else ""
    return match, service_name, username, email


def format_secret_path(service_name: str, entry: dict) -> str:
    """
    Build a shortcut path string for an entry.

    Format: ``<service>/<primary_identifier>``
    """
    t = entry.get("secret_type", TYPE_LOGIN)

    if t == TYPE_LOGIN:
        username = entry.get("username", "").strip()
        email    = entry.get("email",    "").strip()
        parts    = [service_name, username]
        if email:
            parts.append(email)
        return "/".join(parts)

    if t == TYPE_API_KEY:
        return f"{service_name}/{entry.get('key_name', '').strip()}"

    if t == TYPE_SECURE_NOTE:
        return f"{service_name}/{entry.get('title', '').strip()}"

    if t == TYPE_SSH_KEY:
        return f"{service_name}/{entry.get('key_name', '').strip()}"

    return f"{service_name}/{get_display_summary(entry)}"
