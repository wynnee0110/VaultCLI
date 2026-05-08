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
        print("❌ This field is required.")


def _select_provider() -> str:
    while True:
        print("\nDatabase provider:")
        print("  1. Supabase (supported)")
        print("  2. PostgreSQL (coming soon)")
        print("  3. SQLite (coming soon)")

        choice = input("\nSelect provider: ").strip()

        if choice == "1":
            return "supabase"

        if choice in {"2", "3"}:
            print("⚠️  That provider is planned but not available yet. Please choose Supabase for now.")
            continue

        print("❌ Invalid option.")


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

    print("\nSupabase configuration")
    url = _prompt_non_empty("Supabase Project URL")
    anon_key = _prompt_non_empty("Supabase Anon Key")

    try:
        create_db({
            "provider": provider,
            "url": url,
            "anonKey": anon_key,
        })
    except Exception as exc:
        print(f"❌ Could not initialize the Supabase client: {exc}")
        return False

    save_config(provider, url, anon_key)
    reset_db()

    print(f"\n✅ Configuration saved to {CONFIG_FILE}")
    print("\nRun this SQL in the Supabase SQL editor before storing vault data:\n")
    print(SUPABASE_SCHEMA_SQL)
    input("\nPress Enter after you have run or saved the SQL.")

    print("\nSetup complete.")
    print("VaultCLI encrypts your vault locally before anything is written to the database.")
    print("Next step: run `vault login`.")
    return True
