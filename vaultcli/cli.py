import argparse

from vaultcli.commands.auth import (
    command_login,
    command_logout,
    command_signup,
    ensure_configured,
    try_resume_session,
)
from vaultcli.commands.secrets import (
    get_secret_shortcut,
    list_secret_locations,
    store_secret_shortcut,
)
from vaultcli.commands.system import command_update
from vaultcli.commands.interactive import run_vault_app
from vaultcli.commands.init import run_setup_wizard
from vaultcli.ui.prompts import auth_menu

def run_default() -> int:
    print("Welcome to Vault CLI 🔐")

    if not ensure_configured():
        return 1

    user_id = try_resume_session(verbose=False)

    if not user_id:
        while True:
            result = auth_menu()
            if result is None or result == "0":
                print("Bye 👋")
                return 0
            if result == "1":
                from vaultcli.commands.auth import prompt_login
                user_id = prompt_login()
                if user_id:
                    break
            elif result == "2":
                from vaultcli.commands.auth import prompt_signup
                prompt_signup()
            else:
                print("Invalid option")

    run_vault_app(user_id)
    return 0

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vault",
        description="VaultCLI: a secure self-hosted vault manager.",
    )

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("init", help="Run setup wizard: vault init")
    subparsers.add_parser("login", help="Login: vault login")
    subparsers.add_parser("signup", help="Create account: vault signup")
    subparsers.add_parser("logout", help="Logout: vault logout")
    subparsers.add_parser("list", help="List secrets: vault list")
    subparsers.add_parser("update", help="Update CLI: vault update")

    # GET command
    get_parser = subparsers.add_parser("get", help="Get secret: vault get <service>/<title>")
    get_parser.add_argument("path", help="<service>/<title>")

    # PUT command
    put_parser = subparsers.add_parser("put", help="Store secret: vault put <service>/<title> <secret>")
    put_parser.add_argument("path", help="<service>/<title>")
    put_parser.add_argument("secret", help="Secret value")

    return parser

def main(argv=None) -> int:
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
