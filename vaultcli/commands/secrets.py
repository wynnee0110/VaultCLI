import uuid

from vaultcli.core.vault_manager import find_entry_by_path, find_account_by_path, format_secret_path, migrate_vault
from vaultcli.core.secret_types import TYPE_LOGIN
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


def store_secret_shortcut(path: str, secret: str) -> int:
    """
    CLI shortcut: ``vault set <service>/<identifier> <secret>``

    For login  entries the identifier is the username and *secret* is the password.
    For api_key entries the identifier is the key_name and *secret* is the api_key value.
    For ssh_key entries the identifier is the key_name and *secret* is the private_key.
    For secure_note the identifier is the title and *secret* is the note body.

    If the entry doesn't exist yet it is created as a TYPE_LOGIN entry (legacy behaviour).
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

    if existing:
        # Update the relevant secret field based on type
        t = existing.get("secret_type", TYPE_LOGIN)
        field_map = {
            "login":        "password",
            "api_key":      "api_key",
            "secure_note":  "note",
            "ssh_key":      "private_key",
        }
        existing[field_map.get(t, "password")] = secret
        action = "updated"
    else:
        # Create new entry as legacy login type
        accounts = services.setdefault(service_name, [])
        accounts.append({
            "id":          str(uuid.uuid4()),
            "secret_type": TYPE_LOGIN,
            "username":    identifier,
            "email":       "",
            "password":    secret,
        })
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
