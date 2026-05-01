import getpass
import uuid

from auth import login, logout, signup, refresh_session
from session import load_session, clear_session
from vault import get_vault, save_vault, setup_master_password


# ---------------- helpers ----------------

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
                "id":       acc.get("id", str(uuid.uuid4())),
                "username": acc.get("username", ""),
                "email":    acc.get("email", ""),
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

    print("\n📂 Services:")
    for i, name in enumerate(names):
        count = len(services[name])
        print(f"  {i}. {name}  ({count} account{'s' if count != 1 else ''})")

    idx = safe_int("\nSelect service (index): ", len(names))
    if idx is None:
        return None
    return names[idx]


def pick_account(accounts, service_name):
    """Show numbered accounts for a service and return the chosen index."""
    if not accounts:
        print(f"No accounts stored under '{service_name}'.")
        return None

    print(f"\n👤 Accounts in [{service_name}]:")
    for i, acc in enumerate(accounts):
        print(f"  {i}. {acc.get('username', '-')}  ({acc.get('email', '-')})")

    return safe_int("\nSelect account (index): ", len(accounts))


def show_account(acc, service_name):
    """Pretty-print full account details."""
    print("\n" + "─" * 40)
    print(f"  🏷️  Service  : {service_name}")
    print(f"  👤 Username : {acc.get('username', '-')}")
    print(f"  📧 Email    : {acc.get('email', '-')}")
    print(f"  🔑 Password : {acc.get('password', '-')}")
    print("─" * 40)


# ---------------- AUTH FLOW ----------------

def try_resume_session():
    """Returns user_id string on success, None on failure."""
    session = load_session()
    if not session:
        return None
    refresh_token = session.get("refresh_token")
    if refresh_token:
        print("🔄 Resuming session...")
        if refresh_session(refresh_token):
            print("✅ Session restored")
            return session["user"]["id"]
        else:
            print("⚠️  Session expired — please log in again.")
    return None


def setup_master_key(user_id: str):
    """
    Prompt for the master password (up to 3 attempts) and initialise
    the in-memory vault encryption key via PBKDF2.
    """
    for attempt in range(3):
        mp = getpass.getpass("🔑 Master password: ")
        try:
            is_existing = setup_master_password(user_id, mp)
            if not is_existing:
                # New vault — confirm the password so user doesn't lock themselves out
                confirm = getpass.getpass("🔑 Confirm master password: ")
                if mp != confirm:
                    print("❌ Passwords do not match. Try again.")
                    continue
                print("✅ Master password set. Keep it safe — it's the only way to recover your vault.")
            return   # success
        except ValueError:
            remaining = 2 - attempt
            if remaining:
                print(f"❌ Wrong master password. {remaining} attempt(s) left.")
            else:
                print("❌ Too many failed attempts. Exiting.")
                raise SystemExit(1)


def auth_menu():
    print("\n========== VAULT CLI ==========")
    print("1. Login")
    print("2. Sign up")
    print("0. Exit")

    choice = input("\nSelect: ").strip()

    if choice == "1":
        email = input("Email: ").strip()
        password = getpass.getpass("Password: ")
        try:
            res = login(email, password)
            print("✅ Logged in")
            return res.user.id   # return user_id on success
        except Exception as e:
            print(f"❌ Login failed: {e}")
            return False

    elif choice == "2":
        email = input("Email: ").strip()
        password = getpass.getpass("Password (min 6 chars): ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("❌ Passwords do not match.")
            return False
        try:
            res = signup(email, password)
            if res.user:
                print("✅ Account created! Check your email to confirm, then log in.")
            else:
                print("⚠️  Signup may require email confirmation.")
            return False
        except Exception as e:
            print(f"❌ Signup failed: {e}")
            return False

    elif choice == "0":
        return None  # exit signal

    else:
        print("Invalid option")
        return False


# ---------------- MENU ----------------

def menu():
    print("\n========== VAULT CLI ==========")
    print("1. Add account")
    print("2. View accounts")
    print("3. Edit account")
    print("4. Delete account")
    print("5. Search")
    print("6. Logout")
    print("0. Exit")


# ---------------- APP LOOP ----------------

def main():
    print("Welcome to Vault CLI 🔐")

    user_id = try_resume_session()

    if not user_id:
        while True:
            result = auth_menu()
            if result is None:
                print("Bye 👋")
                return
            if isinstance(result, str):   # auth_menu now returns user_id on success
                user_id = result
                break

    # Unlock the vault with the master password (once per session)
    setup_master_key(user_id)

    while True:
        menu()
        choice = input("\nSelect option: ").strip()

        vault, user_id = load_data()
        if not user_id:
            print("❌ Not logged in")
            break

        # Migrate old format if needed (once per load)
        vault = migrate_vault(vault)
        services = vault["services"]

        # ─────────── ADD ───────────
        if choice == "1":
            names = sorted(services.keys())

            print("\n📂 Existing services:")
            for i, name in enumerate(names):
                print(f"  {i}. {name}")
            print(f"  {len(names)}. ➕ Add new service")

            idx = safe_int("\nSelect (index): ", len(names) + 1)
            if idx is None:
                continue

            if idx == len(names):
                service_name = input("New service name: ").strip()
                if not service_name:
                    print("❌ Service name cannot be empty.")
                    continue
            else:
                service_name = names[idx]

            print(f"\nAdding account to [{service_name}]")
            username = input("Username: ").strip()
            email    = input("Email: ").strip()
            password = getpass.getpass("Password: ")

            entry = {
                "id":       str(uuid.uuid4()),
                "username": username,
                "email":    email,
                "password": password,
            }

            services.setdefault(service_name, []).append(entry)
            save_vault(user_id, vault)
            print(f"✅ Account saved under [{service_name}]")

        # ─────────── VIEW ───────────
        elif choice == "2":
            if not services:
                print("No services stored yet.")
                continue

            service_name = pick_service(services)
            if service_name is None:
                continue

            accounts = services[service_name]
            acc_idx = pick_account(accounts, service_name)
            if acc_idx is None:
                continue

            show_account(accounts[acc_idx], service_name)

        # ─────────── EDIT ───────────
        elif choice == "3":
            if not services:
                print("No services stored yet.")
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
            acc["email"]    = input(f"Email ({acc['email']}): ").strip()       or acc["email"]
            new_pass        = getpass.getpass("New password (blank to keep): ")
            if new_pass:
                acc["password"] = new_pass

            save_vault(user_id, vault)
            print("✅ Updated")

        # ─────────── DELETE ───────────
        elif choice == "4":
            if not services:
                print("No services stored yet.")
                continue

            service_name = pick_service(services)
            if service_name is None:
                continue

            accounts = services[service_name]

            print(f"\nDelete options for [{service_name}]:")
            print("  a. Delete a specific account")
            print("  b. Delete the entire service")
            sub = input("Choice (a/b): ").strip().lower()

            if sub == "a":
                acc_idx = pick_account(accounts, service_name)
                if acc_idx is None:
                    continue
                acc = accounts[acc_idx]
                confirm = input(f"Delete '{acc.get('username', '-')}'? (y/N): ").strip().lower()
                if confirm == "y":
                    accounts.pop(acc_idx)
                    # Remove service key if no accounts remain
                    if not accounts:
                        del services[service_name]
                    save_vault(user_id, vault)
                    print("🗑️  Deleted.")
                else:
                    print("Cancelled.")

            elif sub == "b":
                confirm = input(f"Delete entire service '{service_name}' and ALL its accounts? (y/N): ").strip().lower()
                if confirm == "y":
                    del services[service_name]
                    save_vault(user_id, vault)
                    print(f"🗑️  Service '{service_name}' deleted.")
                else:
                    print("Cancelled.")

            else:
                print("Invalid option.")

        # ─────────── SEARCH ───────────
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

        # ─────────── LOGOUT ───────────
        elif choice == "6":
            try:
                logout()
            except Exception:
                pass
            clear_session()
            print("👋 Logged out.")
            break

        # ─────────── EXIT ───────────
        elif choice == "0":
            print("Bye 👋")
            break

        else:
            print("Invalid option")


if __name__ == "__main__":
    main()