import uuid

from vaultcli.core.vault_manager import find_account_by_path, format_secret_path, migrate_vault
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
        print("❌ Could not save vault data.")
        print("Make sure the Supabase `vaults` table and policies from `vault init` are in place.")
        print(f"Details: {exc}")
        return False

def store_secret_shortcut(path: str, secret: str) -> int:
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
        print("❌ Could not load vault data.")
        print("Make sure the Supabase `vaults` table and policies from `vault init` are in place.")
        print(f"Details: {exc}")
        return 1

    try:
        _, service_name, username, email = find_account_by_path(vault, path)
    except ValueError as exc:
        print(f"❌ {exc}")
        return 1

    vault = migrate_vault(vault)
    services = vault["services"]
    accounts = services.setdefault(service_name, [])

    existing = next(
        (
            acc for acc in accounts
            if acc.get("username", "") == username and acc.get("email", "") == email
        ),
        None,
    )

    if existing:
        existing["password"] = secret
        action = "updated"
    else:
        accounts.append({
            "id": str(uuid.uuid4()),
            "username": username,
            "email": email,
            "password": secret,
        })
        action = "stored"

    if not persist_vault(user_id, vault):
        return 1

    print(f"✅ Secret {action} for {service_name}/{username}")
    if email:
        print(f"   Email: {email}")
    return 0

def get_secret_shortcut(path: str) -> int:
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
        print("❌ Could not load vault data.")
        print("Make sure the Supabase `vaults` table and policies from `vault init` are in place.")
        print(f"Details: {exc}")
        return 1

    try:
        match, _, _, _ = find_account_by_path(vault, path)
    except ValueError as exc:
        print(f"❌ {exc}")
        return 1

    if not match:
        print("❌ Secret not found.")
        return 1

    print(match.get("password", ""))
    return 0

def list_secret_locations() -> int:
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
        print("❌ Could not load vault data.")
        print("Make sure the Supabase `vaults` table and policies from `vault init` are in place.")
        print(f"Details: {exc}")
        return 1

    vault = migrate_vault(vault)
    services = vault["services"]
    secret_paths = []

    for service_name, accounts in sorted(services.items()):
        for account in accounts:
            secret_paths.append(format_secret_path(service_name, account))

    if not secret_paths:
        print("No secrets stored yet.")
        return 0

    for secret_path in sorted(secret_paths):
        print(secret_path)

    return 0
