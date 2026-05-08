import getpass
import uuid

from vaultcli.core.vault_manager import migrate_vault
from vaultcli.core.session import clear_session
from vaultcli.crypto.vault import clear_master_key
from vaultcli.api.supabase_auth import logout
from vaultcli.ui.prompts import menu, safe_int, pick_service, pick_account
from vaultcli.ui.formatters import show_account
from vaultcli.commands.auth import setup_master_key
from vaultcli.commands.secrets import load_data, persist_vault

def run_vault_app(user_id: str):
    setup_master_key(user_id)

    while True:
        choice = menu()

        try:
            vault, current_user_id = load_data()
        except Exception as exc:
            print("❌ Could not load vault data.")
            print("Make sure the Supabase `vaults` table and policies from `vault init` are in place.")
            print(f"Details: {exc}")
            break
        if not current_user_id:
            print("❌ Not logged in")
            break

        vault = migrate_vault(vault)
        services = vault["services"]

        if choice == "add":
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

        elif choice == "view":
            if not services:
                print("No secrets stored yet.")
                continue

            service_name = pick_service(services)
            if service_name is None:
                continue

            accounts = services[service_name]
            acc_idx = pick_account(accounts, service_name)
            if acc_idx is None or acc_idx == -1:
                continue

            show_account(accounts[acc_idx], service_name)

        elif choice == "edit":
            if not services:
                print("No secrets stored yet.")
                continue

            service_name = pick_service(services)
            if service_name is None:
                continue

            accounts = services[service_name]
            acc_idx = pick_account(accounts, service_name)
            if acc_idx is None or acc_idx == -1:
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

        elif choice == "delete":
            if not services:
                print("No secrets stored yet.")
                continue

            service_name = pick_service(services)
            if service_name is None:
                continue

            accounts = services[service_name]

            print(f"\nDelete options for [{service_name}]:")
            print("  a. Delete a specific secret")
            print("  b. Delete the entire service")
            sub = input("Choice (a/b): ").strip().lower()

            if sub == "a":
                acc_idx = pick_account(accounts, service_name)
                if acc_idx is None or acc_idx == -1:
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

        elif choice == "logout":
            try:
                logout()
            except Exception:
                pass
            clear_master_key()
            clear_session()
            print("👋 Logged out.")
            break

        elif choice == "exit":
            print("Bye 👋")
            break

        else:
            print("Invalid option")
