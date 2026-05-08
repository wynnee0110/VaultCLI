import getpass

from vaultcli.core.config import ConfigError, load_config
from vaultcli.core.session import load_session, clear_session
from vaultcli.api.supabase_db import restore_db_session
from vaultcli.api.supabase_auth import login, signup, logout, refresh_session
from vaultcli.crypto.vault import (
    clear_master_key,
    is_master_key_unlocked,
    setup_master_password,
    try_restore_master_key,
)

def get_user_id() -> str | None:
    session = load_session()
    if not session:
        return None
    user = session.get("user")
    if not user:
        return None
    return user.get("id")

def ensure_configured() -> bool:
    try:
        load_config()
        return True
    except ConfigError as exc:
        print(f"❌ {exc}")
        return False

def try_resume_session(verbose: bool = True) -> str | None:
    """Returns user_id string on success, None on failure."""
    session = load_session()
    if not session:
        return None

    access_token = session.get("access_token")
    refresh_token = session.get("refresh_token")
    if not refresh_token:
        return None

    if access_token:
        try:
            restore_db_session(access_token, refresh_token)
            latest = load_session()
            if latest and latest.get("user"):
                if verbose:
                    print("✅ Session restored")
                return latest["user"]["id"]
        except Exception:
            pass

    if verbose:
        print("🔄 Resuming session...")
    if refresh_session(refresh_token):
        latest = load_session()
        if latest and latest.get("user"):
            new_access = latest.get("access_token")
            new_refresh = latest.get("refresh_token")
            if new_access and new_refresh:
                restore_db_session(new_access, new_refresh)
            if verbose:
                print("✅ Session refreshed")
            return latest["user"]["id"]

    if verbose:
        print("⚠️  Session expired — please log in again.")
    clear_master_key()
    clear_session()
    return None

def setup_master_key(user_id: str, verbose: bool = True):
    if try_restore_master_key(user_id):
        if verbose:
            print("✅ Vault unlocked from trusted local session.")
        return

    if is_master_key_unlocked():
        return

    for attempt in range(3):
        mp = getpass.getpass("🔑 Master password: ")
        try:
            is_existing = setup_master_password(user_id, mp)
            if is_existing:
                if verbose:
                    print("🔑 Master password confirmed.")
            else:
                confirm = getpass.getpass("🔑 Confirm master password: ")
                if mp != confirm:
                    print("❌ Passwords do not match. Try again.")
                    continue
                if verbose:
                    print("✅ Master password set. Keep it safe — it's the only way to recover your vault.")
            return
        except ValueError:
            remaining = 2 - attempt
            if remaining:
                print(f"❌ Wrong master password. {remaining} attempt(s) left.")
            else:
                print("❌ Too many failed attempts. Exiting.")
                raise SystemExit(1)
        except Exception as exc:
            print("❌ Could not open the remote vault store.")
            print("Make sure you ran the SQL from `vault init` in your Supabase project.")
            print(f"Details: {exc}")
            raise SystemExit(1)

def prompt_login() -> str | None:
    email = input("Email: ").strip()
    password = getpass.getpass("Password: ")
    try:
        result = login(email, password)
        if not result.user:
            print("❌ Login failed.")
            return None
        session = load_session()
        if session:
            restore_db_session(
                session.get("access_token", ""),
                session.get("refresh_token", ""),
            )
        print("✅ Logged in")
        return result.user.id
    except Exception as exc:
        print(f"❌ Login failed: {exc}")
        return None

def prompt_signup() -> bool:
    email = input("Email: ").strip()
    password = getpass.getpass("Password (min 6 chars): ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("❌ Passwords do not match.")
        return False

    try:
        result = signup(email, password)
        if result.user:
            print("✅ Account created! Check your email to confirm, then run `vault login`.")
        else:
            print("⚠️  Signup may require email confirmation before login.")
        return True
    except Exception as exc:
        print(f"❌ Signup failed: {exc}")
        return False

def command_login() -> int:
    if not ensure_configured():
        return 1

    user_id = try_resume_session()
    if not user_id:
        user_id = prompt_login()
        if not user_id:
            return 1

    from vaultcli.commands.interactive import run_vault_app
    run_vault_app(user_id)
    return 0

def command_signup() -> int:
    if not ensure_configured():
        return 1
    return 0 if prompt_signup() else 1

def command_logout() -> int:
    clear_master_key()
    if not ensure_configured():
        clear_session()
        return 1

    try:
        logout()
    except Exception:
        pass

    clear_session()
    print("👋 Logged out.")
    return 0
