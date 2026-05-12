import uuid

from vaultcli.core.vault_manager import find_entry_by_path, find_account_by_path, format_secret_path, migrate_vault
from vaultcli.core.secret_types import TYPE_LOGIN, TYPE_API_KEY, TYPE_SECURE_NOTE, TYPE_SSH_KEY
from vaultcli.crypto.vault import get_vault, save_vault
from vaultcli.commands.auth import ensure_configured, get_user_id, prompt_login, try_resume_session, setup_master_key


def load_data() -> tuple[dict, str | None]:
    user_id = get_user_id()
    if not user_id:
        return {}, None
    return get_vault(user_id), user_id


def persist_vault(user_id: str, vault: dict) -> bool:
    try:
        save_vault(user_id, vault)
        return True
    except Exception as exc:
        print("Could not save vault data.")
        print("Make sure the Supabase `vaults` table and policies from `vault init` are in place.")
        print(f"Details: {exc}")
        return False


def store_secret_shortcut(path: str, secret: str, secret_type: str | None = None) -> int:
    """
    CLI shortcut: ``vault put <service>/<identifier> <value> [--type TYPE]``

    The identifier and stored field depend on the type:

    +--------------+-------------+----------------------------+
    | Type         | Identifier  | Field that stores <value>  |
    +==============+=============+============================+
    | login        | username    | password                   |
    | api_key      | key_name    | api_key                    |
    | secure_note  | title       | note                       |
    | ssh_key      | key_name    | private_key                |
    +--------------+-------------+----------------------------+

    ``secret_type`` only matters when *creating* a brand-new entry.
    For existing entries the stored type is preserved and the matching
    field is updated regardless of the ``--type`` flag.
    """
    if not ensure_configured():
        return 1

    user_id = try_resume_session(verbose=False)
    if not user_id:
        user_id = prompt_login()
        if not user_id:
            return 1

    setup_master_key(user_id, verbose=False)

    try:
        vault, _ = load_data()
    except Exception as exc:
        print("Could not load vault data.")
        print("Make sure the Supabase `vaults` table and policies from `vault init` are in place.")
        print(f"Details: {exc}")
        return 1

    vault    = migrate_vault(vault)
    services = vault["services"]

    existing, service_name, identifier = find_entry_by_path(vault, path)

    # Map type → which field holds the primary secret value
    field_map = {
        TYPE_LOGIN:       "password",
        TYPE_API_KEY:     "api_key",
        TYPE_SECURE_NOTE: "note",
        TYPE_SSH_KEY:     "private_key",
    }

    if existing:
        # Update the relevant secret field, preserving the existing type
        t = existing.get("secret_type", TYPE_LOGIN)
        existing[field_map.get(t, "password")] = secret
        action = "updated"
    else:
        # Create a new entry using the requested (or default) type
        new_type = secret_type or TYPE_LOGIN
        value_field = field_map.get(new_type, "password")

        # Build skeleton for the chosen type — required fields get a placeholder
        new_entry: dict = {
            "id":          str(uuid.uuid4()),
            "secret_type": new_type,
        }

        if new_type == TYPE_LOGIN:
            new_entry["username"] = identifier
            new_entry["email"]    = ""
            new_entry["password"] = secret

        elif new_type == TYPE_API_KEY:
            new_entry["key_name"] = identifier
            new_entry["api_key"]  = secret

        elif new_type == TYPE_SECURE_NOTE:
            new_entry["title"] = identifier
            new_entry["note"]  = secret

        elif new_type == TYPE_SSH_KEY:
            new_entry["key_name"]    = identifier
            new_entry["private_key"] = secret
            new_entry["public_key"]  = ""
            new_entry["passphrase"]  = ""

        services.setdefault(service_name, []).append(new_entry)
        action = "stored"

    if not persist_vault(user_id, vault):
        return 1

    print(f"Secret {action} for {service_name}/{identifier}")
    return 0


def get_secret_shortcut(path: str) -> int:
    """CLI shortcut: ``vault get <service>/<identifier>`` — prints the secret value."""
    if not ensure_configured():
        return 1

    user_id = try_resume_session(verbose=False)
    if not user_id:
        user_id = prompt_login()
        if not user_id:
            return 1

    setup_master_key(user_id, verbose=False)

    try:
        vault, _ = load_data()
    except Exception as exc:
        print("Could not load vault data.")
        print("Make sure the Supabase `vaults` table and policies from `vault init` are in place.")
        print(f"Details: {exc}")
        return 1

    match, service_name, identifier = find_entry_by_path(vault, path)

    if not match:
        print("Secret not found.")
        return 1

    # Print the primary secret value for the type
    t = match.get("secret_type", TYPE_LOGIN)
    field_map = {
        "login":        "password",
        "api_key":      "api_key",
        "secure_note":  "note",
        "ssh_key":      "private_key",
    }
    print(match.get(field_map.get(t, "password"), ""))
    return 0


def list_secret_locations() -> int:
    """CLI shortcut: ``vault list`` — prints all secret paths."""
    if not ensure_configured():
        return 1

    user_id = try_resume_session(verbose=False)
    if not user_id:
        user_id = prompt_login()
        if not user_id:
            return 1

    setup_master_key(user_id, verbose=False)

    try:
        vault, _ = load_data()
    except Exception as exc:
        print("Could not load vault data.")
        print("Make sure the Supabase `vaults` table and policies from `vault init` are in place.")
        print(f"Details: {exc}")
        return 1

    vault    = migrate_vault(vault)
    services = vault["services"]
    secret_paths = []

    for service_name, accounts in sorted(services.items()):
        for entry in accounts:
            secret_paths.append(format_secret_path(service_name, entry))

    if not secret_paths:
        print("No secrets stored yet.")
        return 0

    for secret_path in sorted(secret_paths):
        print(secret_path)

    return 0
