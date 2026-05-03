import argparse
import getpass
import hashlib
import os
import stat
import sys
import tempfile
import uuid

import requests

from . import __version__
from .auth import login, logout, refresh_session, signup
from .config import ConfigError
from .db import restore_db_session
from .session import clear_session, load_session
from .setup_wizard import run_setup_wizard
from .vault import (
    clear_master_key,
    get_vault,
    is_master_key_unlocked,
    save_vault,
    setup_master_password,
    try_restore_master_key,
)

VERSION = __version__
GITHUB_REPO = "wynnee0110/VaultCli"
LATEST_RELEASE_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases"
REQUEST_HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": f"VaultCLI/{VERSION}",
}


def _normalize_version(version: str) -> str:
    return version[1:] if version.startswith("v") else version


def _platform_asset_candidates(current_name: str | None = None) -> list[str]:
    candidates: list[str] = []
    if current_name:
        candidates.append(current_name)

    if sys.platform.startswith("linux"):
        candidates.extend(["vault-linuxV1", "vault-linux"])
    elif sys.platform == "darwin":
        candidates.extend(["vault-macosV1", "vault-macos"])
    elif sys.platform == "win32":
        candidates.extend(["vault-windowsV1.exe", "vault-windows.exe"])
    else:
        raise RuntimeError(f"Unsupported OS: {sys.platform}")

    seen = set()
    unique_candidates = []
    for candidate in candidates:
        if candidate and candidate not in seen:
            unique_candidates.append(candidate)
            seen.add(candidate)
    return unique_candidates


def _current_install_path() -> str | None:
    if getattr(sys, "frozen", False):
        return os.path.realpath(sys.executable)

    current_path = os.path.realpath(sys.argv[0])
    basename = os.path.basename(current_path)

    if basename.endswith(".py") or basename in {"pyinstaller_entry.py", "__main__.py"}:
        return None

    return current_path if os.path.isfile(current_path) else None


def _download_release(asset_url: str) -> bytes:
    response = requests.get(asset_url, headers=REQUEST_HEADERS, timeout=60)
    response.raise_for_status()
    return response.content


def _download_release_text(asset_url: str) -> str:
    response = requests.get(asset_url, headers=REQUEST_HEADERS, timeout=30)
    response.raise_for_status()
    return response.text


def _find_checksum_asset(assets: dict[str, str], asset_name: str) -> tuple[str | None, str | None]:
    candidates = [
        f"{asset_name}.sha256",
        f"{asset_name}.sha256.txt",
        "SHA256SUMS",
        "SHA256SUMS.txt",
        "sha256sums.txt",
    ]
    for candidate in candidates:
        if candidate in assets:
            return candidate, assets[candidate]
    return None, None


def _extract_checksum(checksum_text: str, asset_name: str) -> str | None:
    for line in checksum_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        parts = stripped.split()
        if len(parts) == 1 and len(parts[0]) == 64:
            return parts[0].lower()

        if len(parts) >= 2:
            candidate_hash = parts[0].lower()
            candidate_name = parts[-1].lstrip("*")
            if (
                len(candidate_hash) == 64
                and all(ch in "0123456789abcdef" for ch in candidate_hash)
                and candidate_name == asset_name
            ):
                return candidate_hash

    return None


def _sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _replace_installed_binary(target_path: str, payload: bytes):
    target_dir = os.path.dirname(target_path) or "."
    fd, temp_path = tempfile.mkstemp(prefix=".vault-update-", dir=target_dir)

    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)

        current_mode = 0o755
        if os.path.exists(target_path):
            current_mode = stat.S_IMODE(os.stat(target_path).st_mode)
        os.chmod(temp_path, current_mode | 0o755)
        os.replace(temp_path, target_path)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)



def update():
    print("Checking for updates...")

    try:
        response = requests.get(LATEST_RELEASE_API_URL, headers=REQUEST_HEADERS, timeout=15)
        response.raise_for_status()
        release = response.json()
    except requests.RequestException as exc:
        print(f"❌ Could not check for updates: {exc}")
        return 1

    latest_version = release.get("tag_name")
    if not latest_version:
        print("❌ Latest release information is unavailable.")
        return 1

    if _normalize_version(latest_version) == _normalize_version(VERSION):
        print("✅ Already up to date")
        return 0

    print(f"⬆️ Updating from {VERSION} → {latest_version}")

    current_path = _current_install_path()
    if not current_path:
        print("❌ Self-update only works from an installed VaultCLI executable.")
        print(f"Download the latest binary from: {RELEASES_URL}")
        return 1

    current_name = os.path.basename(current_path)

    try:
        asset_candidates = _platform_asset_candidates(current_name)
    except RuntimeError as exc:
        print(f"❌ {exc}")
        return 1

    assets = {
        asset.get("name"): asset.get("browser_download_url")
        for asset in release.get("assets", [])
        if asset.get("name") and asset.get("browser_download_url")
    }

    asset_name = next((name for name in asset_candidates if name in assets), None)
    download_url = assets.get(asset_name) if asset_name else None

    if not download_url:
        print("❌ Could not find binary")
        print(f"Expected one of: {', '.join(asset_candidates)}")
        return 1

    checksum_asset_name, checksum_url = _find_checksum_asset(assets, asset_name)
    if not checksum_url:
        print("❌ Release is missing a checksum asset.")
        print(f"Expected {asset_name}.sha256 or a SHA256SUMS file in {RELEASES_URL}.")
        return 1

    print(f"Downloading update ({asset_name})...")

    try:
        binary = _download_release(download_url)
    except requests.RequestException as exc:
        print(f"❌ Could not download update: {exc}")
        return 1

    try:
        checksum_text = _download_release_text(checksum_url)
    except requests.RequestException as exc:
        print(f"❌ Could not download checksum asset {checksum_asset_name}: {exc}")
        return 1

    expected_checksum = _extract_checksum(checksum_text, asset_name)
    if not expected_checksum:
        print(f"❌ Could not parse a SHA-256 checksum for {asset_name} from {checksum_asset_name}.")
        return 1

    actual_checksum = _sha256_hex(binary)
    if actual_checksum != expected_checksum:
        print("❌ Downloaded binary checksum mismatch.")
        return 1

    try:
        _replace_installed_binary(current_path, binary)
    except OSError as exc:
        print(f"❌ Could not replace executable at {current_path}: {exc}")
        return 1

    print("✅ Update complete! Restart CLI.")
    return 0


def get_user_id():
    session = load_session()
    if not session:
        return None
    user = session.get("user")
    if not user:
        return None
    return user.get("id")


def load_data():
    user_id = get_user_id()
    if not user_id:
        return {}, None
    return get_vault(user_id), user_id


def safe_int(prompt, max_index):
    """Prompt for a number and validate it's within range. Returns None on bad input."""
    try:
        val = int(input(prompt))
        if val < 0 or val >= max_index:
            print(f"❌ Invalid. Must be 0 – {max_index - 1}.")
            return None
        return val
    except ValueError:
        print("❌ Please enter a number.")
        return None


def migrate_vault(vault):
    """
    Migrate old flat-list vault {"accounts": [...]} to the new
    service-grouped format {"services": {"AppName": [...]}}.
    """
    if "accounts" in vault and "services" not in vault:
        print("🔄 Migrating vault to new format...")
        services = {}
        for acc in vault["accounts"]:
            app = acc.get("app", "Unknown")
            entry = {
                "id": acc.get("id", str(uuid.uuid4())),
                "username": acc.get("username", ""),
                "email": acc.get("email", ""),
                "password": acc.get("password", ""),
            }
            services.setdefault(app, []).append(entry)
        vault = {"services": services}
        print("✅ Migration complete.\n")
    elif "services" not in vault:
        vault = {"services": {}}
    return vault


def pick_service(services):
    """Show a numbered list of services and return the chosen name."""
    names = sorted(services.keys())
    if not names:
        print("No services stored yet.")
        return None

    print("\n📂 Secrets:")
    for i, name in enumerate(names):
        count = len(services[name])
        print(f"  {i}. {name}  ({count} secret{'s' if count != 1 else ''})")

    idx = safe_int("\nSelect service (index): ", len(names))
    if idx is None:
        return None
    return names[idx]


def pick_account(accounts, service_name):
    """Show numbered accounts for a service and return the chosen index."""
    if not accounts:
        print(f"No accounts stored under '{service_name}'.")
        return None

    print(f"\n👤 Secrets in [{service_name}]:")
    for i, acc in enumerate(accounts):
        print(f"  {i}. {acc.get('username', '-')}  ({acc.get('email', '-')})")

    return safe_int("\nSelect secret (index): ", len(accounts))


def show_account(acc, service_name):
    """Pretty-print full account details."""
    print("\n" + "─" * 40)
    print(f"  🏷️  Service  : {service_name}")
    print(f"  👤 Username : {acc.get('username', '-')}")
    print(f"  📧 Email    : {acc.get('email', '-')}")
    print(f"  🔑 Password : {acc.get('password', '-')}")
    print("─" * 40)


def ensure_configured() -> bool:
    try:
        from .config import load_config

        load_config()
        return True
    except ConfigError as exc:
        print(f"❌ {exc}")
        return False


def try_resume_session(verbose: bool = True):
    """Returns user_id string on success, None on failure."""
    session = load_session()
    if not session:
        return None

    access_token = session.get("access_token")
    refresh_token = session.get("refresh_token")
    if not refresh_token:
        return None

    # Try to restore the existing access token first
    if access_token:
        try:
            restore_db_session(access_token, refresh_token)
            # Verify it's still valid by fetching the user
            latest = load_session()
            if latest and latest.get("user"):
                if verbose:
                    print("✅ Session restored")
                return latest["user"]["id"]
        except Exception:
            pass

    # Access token stale — try refresh
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
    """
    Prompt for the master password (up to 3 attempts) and initialise
    the in-memory vault encryption key via PBKDF2.
    """
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


def prompt_login():
    email = input("Email: ").strip()
    password = getpass.getpass("Password: ")
    try:
        result = login(email, password)
        if not result.user:
            print("❌ Login failed.")
            return None
        # Inject the fresh tokens into the DB client immediately
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


def prompt_signup():
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


def auth_menu():
    print("1. Login")
    print("2. Sign up")
    print("0. Exit")

    choice = input("\nSelect: ").strip()

    if choice == "1":
        return prompt_login()

    if choice == "2":
        prompt_signup()
        return False

    if choice == "0":
        return None

    print("Invalid option")
    return False


def menu():
   
    print("1. Add Secret")
    print("2. View Secrets")
    print("3. Edit Secret")
    print("4. Delete Secret")
    print("5. Search")
    print("6. Logout")
    print("0. Exit")


def persist_vault(user_id: str, vault: dict) -> bool:
    try:
        save_vault(user_id, vault)
        return True
    except Exception as exc:
        print("❌ Could not save vault data.")
        print("Make sure the Supabase `vaults` table and policies from `vault init` are in place.")
        print(f"Details: {exc}")
        return False


def parse_secret_path(path: str) -> tuple[str, str, str]:
    parts = [part.strip() for part in path.split("/")]
    if len(parts) == 2:
        service_name, username = parts
        if not service_name or not username:
            raise ValueError("Path must look like <service>/<username>.")
        return service_name, username, ""
    if len(parts) == 3:
        service_name, username, email = parts
        if not service_name or (not username and not email):
            raise ValueError(
                "Path must look like <service>/<username>/<email> when using three segments."
            )
        return service_name, username, email
    raise ValueError(
        "Path must look like <service>/<username> or <service>/<username>/<email>."
    )


def find_account_by_path(vault: dict, path: str) -> tuple[dict | None, str, str, str]:
    service_name, username, email = parse_secret_path(path)
    vault = migrate_vault(vault)
    services = vault["services"]
    accounts = services.get(service_name, [])

    match = next(
        (
            acc for acc in accounts
            if acc.get("username", "") == username and acc.get("email", "") == email
        ),
        None,
    )
    return match, service_name, username, email


def format_secret_path(service_name: str, account: dict) -> str:
    username = account.get("username", "").strip()
    email = account.get("email", "").strip()
    path_parts = [service_name, username]
    if email:
        path_parts.append(email)
    return "/".join(path_parts)


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


def run_vault_app(user_id: str):
    setup_master_key(user_id)

    while True:
        menu()
        choice = input("\nSelect option: ").strip()

        try:
            vault, user_id = load_data()
        except Exception as exc:
            print("❌ Could not load vault data.")
            print("Make sure the Supabase `vaults` table and policies from `vault init` are in place.")
            print(f"Details: {exc}")
            break
        if not user_id:
            print("❌ Not logged in")
            break

        vault = migrate_vault(vault)
        services = vault["services"]

        if choice == "1":
            names = sorted(services.keys())

            print("\n📂 Existing Secrets:")
            for i, name in enumerate(names):
                print(f"  {i}. {name}")
            print(f"  {len(names)}. ➕ Add new secret")

            idx = safe_int("\nSelect (index): ", len(names) + 1)
            if idx is None:
                continue

            if idx == len(names):
                service_name = input("New secret name: ").strip()
                if not service_name:
                    print("❌ Service name cannot be empty.")
                    continue
            else:
                service_name = names[idx]

            print(f"\nAdding account to [{service_name}]")
            username = input("Username: ").strip()
            email = input("Email: ").strip()
            password = getpass.getpass("Password: ")

            entry = {
                "id": str(uuid.uuid4()),
                "username": username,
                "email": email,
                "password": password,
            }

            services.setdefault(service_name, []).append(entry)
            if persist_vault(user_id, vault):
                print(f"✅ Secret saved under [{service_name}]")

        elif choice == "2":
            if not services:
                print("No secrets stored yet.")
                continue

            service_name = pick_service(services)
            if service_name is None:
                continue

            accounts = services[service_name]
            acc_idx = pick_account(accounts, service_name)
            if acc_idx is None:
                continue

            show_account(accounts[acc_idx], service_name)

        elif choice == "3":
            if not services:
                print("No secrets stored yet.")
                continue

            service_name = pick_service(services)
            if service_name is None:
                continue

            accounts = services[service_name]
            acc_idx = pick_account(accounts, service_name)
            if acc_idx is None:
                continue

            acc = accounts[acc_idx]
            print(f"\nEditing [{service_name}] → {acc.get('username', '-')}  (leave blank to keep current)")

            acc["username"] = input(f"Username ({acc['username']}): ").strip() or acc["username"]
            acc["email"] = input(f"Email ({acc['email']}): ").strip() or acc["email"]
            new_pass = getpass.getpass("New password (blank to keep): ")
            if new_pass:
                acc["password"] = new_pass

            if persist_vault(user_id, vault):
                print("✅ Updated")

        elif choice == "4":
            if not services:
                print("No secrets stored yet.")
                continue

            service_name = pick_service(services)
            if service_name is None:
                continue

            accounts = services[service_name]

            print(f"\nDelete options for [{service_name}]:")
            print("  a. Delete a specific secret")
            print("  b. Delete the entire secret")
            sub = input("Choice (a/b): ").strip().lower()

            if sub == "a":
                acc_idx = pick_account(accounts, service_name)
                if acc_idx is None:
                    continue
                acc = accounts[acc_idx]
                confirm = input(f"Delete '{acc.get('username', '-')}'? (y/N): ").strip().lower()
                if confirm == "y":
                    accounts.pop(acc_idx)
                    if not accounts:
                        del services[service_name]
                    if persist_vault(user_id, vault):
                        print("🗑️  Deleted.")
                else:
                    print("Cancelled.")

            elif sub == "b":
                confirm = input(f"Delete entire service '{service_name}' and ALL its accounts? (y/N): ").strip().lower()
                if confirm == "y":
                    del services[service_name]
                    if persist_vault(user_id, vault):
                        print(f"🗑️  Service '{service_name}' deleted.")
                else:
                    print("Cancelled.")

            else:
                print("Invalid option.")

        elif choice == "5":
            query = input("Search (service, username, or email): ").strip().lower()
            if not query:
                continue

            found = False
            for svc, accounts in sorted(services.items()):
                matches = [
                    (i, acc) for i, acc in enumerate(accounts)
                    if query in svc.lower()
                    or query in acc.get("username", "").lower()
                    or query in acc.get("email", "").lower()
                ]
                if matches:
                    found = True
                    print(f"\n📂 {svc}")
                    for i, acc in matches:
                        print(f"   {i}. 👤 {acc.get('username', '-')}  ({acc.get('email', '-')})")
                        show_pw = input("      Show password? (y/N): ").strip().lower()
                        if show_pw == "y":
                            print(f"      🔑 {acc.get('password', '-')}")

            if not found:
                print("No matching accounts.")

        elif choice == "6":
            try:
                logout()
            except Exception:
                pass
            clear_master_key()
            clear_session()
            print("👋 Logged out.")
            break

        elif choice == "0":
            print("Bye 👋")
            break

        else:
            print("Invalid option")

def command_update():
    update()
    return 0

def command_login():
    if not ensure_configured():
        return 1

    user_id = try_resume_session()
    if not user_id:
        user_id = prompt_login()
        if not user_id:
            return 1

    run_vault_app(user_id)
    return 0


def command_signup():
    if not ensure_configured():
        return 1
    return 0 if prompt_signup() else 1


def command_logout():
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


def run_default():
    print("Welcome to Vault CLI 🔐")

    if not ensure_configured():
        return 1

    user_id = try_resume_session()

    if not user_id:
        while True:
            result = auth_menu()
            if result is None:
                print("Bye 👋")
                return 0
            if isinstance(result, str):
                user_id = result
                break

    run_vault_app(user_id)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="vault",
        description="VaultCLI: a secure self-hosted vault manager.",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("init", help="Run the VaultCLI setup wizard.")
    subparsers.add_parser("login", help="Log in and open your vault.")
    subparsers.add_parser("signup", help="Create a VaultCLI account.")
    subparsers.add_parser("logout", help="Clear the current session.")
    subparsers.add_parser("list", help="List all stored secret paths.")
    subparsers.add_parser("update", help="Check for and install the latest VaultCLI release.")
    get_parser = subparsers.add_parser("get", help="Read a secret by path.")
    get_parser.add_argument("path", help="Path like service/username or service/username/email")
    put_parser = subparsers.add_parser("put", help="Store a secret by path.")
    put_parser.add_argument("path", help="Path like service/username or service/username/email")
    put_parser.add_argument("secret", help="Secret value to store")

    return parser


def main(argv=None):
    if argv is None:
        import sys

        argv = sys.argv[1:]

    known_commands = {"init", "login", "signup", "logout", "list", "get", "put", "update"}
    if len(argv) == 2 and argv[0] not in known_commands and not argv[0].startswith("-"):
        return store_secret_shortcut(argv[0], argv[1])

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        return 0 if run_setup_wizard() else 1
    if args.command == "login":
        return command_login()
    if args.command == "signup":
        return command_signup()
    if args.command == "logout":
        return command_logout()
    if args.command == "list":
        return list_secret_locations()
    if args.command == "get":
        return get_secret_shortcut(args.path)
    if args.command == "put":
        return store_secret_shortcut(args.path, args.secret)
    if args.command == "update":
        return command_update()

    return run_default()


if __name__ == "__main__":
    raise SystemExit(main())
