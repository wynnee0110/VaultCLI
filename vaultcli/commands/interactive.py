from vaultcli.core.vault_manager import migrate_vault
from vaultcli.core.session import clear_session
from vaultcli.crypto.vault import clear_master_key
from vaultcli.api.supabase_auth import logout
from vaultcli.ui.prompts import (
    menu,
    pick_service,
    pick_account,
    pick_secret_type,
    collect_new_entry,
    edit_entry,
)
from vaultcli.ui.formatters import show_entry
from vaultcli.commands.auth import setup_master_key
from vaultcli.commands.secrets import load_data, persist_vault


def run_vault_app(user_id: str):
    setup_master_key(user_id)

    while True:
        choice = menu()

        try:
            vault, current_user_id = load_data()
        except Exception as exc:
            print("Could not load vault data.")
            print("Make sure the Supabase `vaults` table and policies from `vault init` are in place.")
            print(f"Details: {exc}")
            break
        if not current_user_id:
            print("Not logged in")
            break

        vault    = migrate_vault(vault)
        services = vault["services"]

        # ------------------------------------------------------------------ ADD
        if choice == "add":
            # 1. Choose or create a service / collection
            names = sorted(services.keys())

            print("\nExisting collections:")
            for i, name in enumerate(names):
                print(f"  {i}. {name}")
            print(f"  {len(names)}. Add new collection")

            try:
                idx = int(input("\nSelect (index): ").strip())
            except ValueError:
                print("Please enter a number.")
                continue

            if idx < 0 or idx > len(names):
                print(f"Invalid. Must be 0 – {len(names)}.")
                continue

            if idx == len(names):
                service_name = input("New collection name: ").strip()
                if not service_name:
                    print("Collection name cannot be empty.")
                    continue
            else:
                service_name = names[idx]

            # 2. Choose secret type
            secret_type = pick_secret_type()
            if not secret_type:
                continue

            # 3. Collect fields
            entry = collect_new_entry(secret_type)
            if entry is None:
                continue

            services.setdefault(service_name, []).append(entry)
            if persist_vault(user_id, vault):
                print(f"Secret saved under [{service_name}]")

        # ----------------------------------------------------------------- VIEW
        elif choice == "view":
            if not services:
                print("No secrets stored yet.")
                continue

            service_name = pick_service(services)
            if service_name is None:
                continue

            accounts = services[service_name]
            acc_idx  = pick_account(accounts, service_name)
            if acc_idx is None or acc_idx == -1:
                continue

            show_entry(accounts[acc_idx], service_name)

        # ----------------------------------------------------------------- EDIT
        elif choice == "edit":
            if not services:
                print("No secrets stored yet.")
                continue

            service_name = pick_service(services)
            if service_name is None:
                continue

            accounts = services[service_name]
            acc_idx  = pick_account(accounts, service_name)
            if acc_idx is None or acc_idx == -1:
                continue

            edit_entry(accounts[acc_idx])

            if persist_vault(user_id, vault):
                print("Updated")

        # --------------------------------------------------------------- DELETE
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
            print("  b. Delete the entire collection")
            sub = input("Choice (a/b): ").strip().lower()

            if sub == "a":
                acc_idx = pick_account(accounts, service_name)
                if acc_idx is None or acc_idx == -1:
                    continue
                acc     = accounts[acc_idx]
                confirm = input(f"Delete this entry? (y/N): ").strip().lower()
                if confirm == "y":
                    accounts.pop(acc_idx)
                    if not accounts:
                        del services[service_name]
                    if persist_vault(user_id, vault):
                        print("Deleted.")
                else:
                    print("Cancelled.")

            elif sub == "b":
                confirm = input(
                    f"Delete entire collection '{service_name}' and ALL its secrets? (y/N): "
                ).strip().lower()
                if confirm == "y":
                    del services[service_name]
                    if persist_vault(user_id, vault):
                        print(f"Collection '{service_name}' deleted.")
                else:
                    print("Cancelled.")

            else:
                print("Invalid option.")

        # --------------------------------------------------------------- LOGOUT
        elif choice == "logout":
            try:
                logout()
            except Exception:
                pass
            clear_master_key()
            clear_session()
            print("Logged out.")
            break

        # ----------------------------------------------------------------- EXIT
        elif choice == "exit":
            print("Bye")
            break

        else:
            print("Invalid option")
