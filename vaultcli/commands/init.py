from __future__ import annotations

from vaultcli.core.config import CONFIG_FILE, ConfigError, config_exists, load_config, save_config
from vaultcli.api.supabase_db import create_db, reset_db


SUPABASE_SCHEMA_SQL = """create table if not exists public.vaults (
  user_id text primary key,
  encrypted_vault text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.vaults enable row level security;

create policy "Users can read their own vault"
  on public.vaults
  for select
  to authenticated
  using ((select auth.uid()::text) = user_id);

create policy "Users can insert their own vault"
  on public.vaults
  for insert
  to authenticated
  with check ((select auth.uid()::text) = user_id);

create policy "Users can update their own vault"
  on public.vaults
  for update
  to authenticated
  using ((select auth.uid()::text) = user_id)
  with check ((select auth.uid()::text) = user_id);"""


def _prompt_non_empty(label: str) -> str:
    while True:
        value = input(f"{label}: ").strip()
        if value:
            return value
        print("This field is required.")


def _select_provider() -> str:
    while True:
        print("\nDatabase provider:")
        print("  1. Supabase (supported)")
        print("  2. Custom Server (supported)")
        print("  3. AWS Cognito + DynamoDB (supported)")
        print("  4. PostgreSQL (coming soon)")
        print("  5. SQLite (coming soon)")

        choice = input("\nSelect provider: ").strip()

        if choice == "1":
            return "supabase"
        if choice == "2":
            return "custom"
        if choice == "3":
            return "aws"

        if choice in {"4", "5"}:
            print("That provider is planned but not available yet. Please choose one of the supported providers.")
            continue

        print("Invalid option.")


def _confirm_overwrite() -> bool:
    if not config_exists():
        return True

    try:
        current = load_config(required=False) or {}
    except ConfigError:
        print("\nExisting configuration file is invalid and will be replaced.")
        return True

    provider = current.get("provider", "unknown")
    url = current.get("url", "unknown")

    print("\nExisting configuration detected:")
    print(f"  Provider: {provider}")
    print(f"  URL: {url}")
    confirm = input("\nOverwrite it? (y/N): ").strip().lower()
    return confirm == "y"


def run_setup_wizard():
    print("VaultCLI setup\n")

    if not _confirm_overwrite():
        print("Setup cancelled.")
        return False

    provider = _select_provider()

    config_payload = {"provider": provider}

    if provider == "supabase":
        print("\nSupabase configuration")
        config_payload["url"] = _prompt_non_empty("Supabase Project URL")
        config_payload["anonKey"] = _prompt_non_empty("Supabase Anon Key")
    elif provider == "custom":
        print("\nCustom Server configuration")
        config_payload["server_url"] = _prompt_non_empty("Server URL (e.g., http://localhost:8000)")
    elif provider == "aws":
        print("\nAWS configuration")
        config_payload["aws_region"] = _prompt_non_empty("AWS Region (e.g., us-east-1)")
        config_payload["aws_cognito_client_id"] = _prompt_non_empty("Cognito App Client ID")
        config_payload["aws_dynamodb_table"] = _prompt_non_empty("DynamoDB Table Name")
        
        # Optional credentials
        access_key = input("AWS Access Key ID (optional, press Enter to skip): ").strip()
        if access_key:
            secret_key = input("AWS Secret Access Key: ").strip()
            config_payload["aws_access_key"] = access_key
            config_payload["aws_secret_key"] = secret_key

    try:
        create_db(config_payload)
    except Exception as exc:
        print(f"Could not initialize the database client: {exc}")
        if provider == "aws":
            print("Note: Ensure you have installed 'boto3' via `pip install boto3` to use AWS.")
        return False

    # Save to config file
    if provider == "supabase":
        save_config(provider, config_payload["url"], config_payload["anonKey"])
    else:
        save_config(provider, **config_payload)
        
    reset_db()

    print(f"\nConfiguration saved to {CONFIG_FILE}")
    
    if provider == "supabase":
        print("\nRun this SQL in the Supabase SQL editor before storing vault data:\n")
        print(SUPABASE_SCHEMA_SQL)
        input("\nPress Enter after you have run or saved the SQL.")
    elif provider == "aws":
        print("\nEnsure your DynamoDB table exists and has a Partition Key named 'user_id' (Type: String).")
        input("\nPress Enter after verifying your AWS environment is ready.")

    print("\nSetup complete.")
    print("VaultCLI encrypts your vault locally before anything is written to the database.")
    print("Next step: run `vault login` or `vault signup` depending on your provider.")
    return True
