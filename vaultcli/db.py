from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from supabase import Client, create_client

from .config import load_config


class VaultDB(ABC):
    """Common interface for VaultCLI database adapters."""

    provider: str

    @abstractmethod
    def signup(self, email: str, password: str):
        raise NotImplementedError

    @abstractmethod
    def login(self, email: str, password: str):
        raise NotImplementedError

    @abstractmethod
    def refresh_session(self, refresh_token: str):
        raise NotImplementedError

    @abstractmethod
    def logout(self):
        raise NotImplementedError

    @abstractmethod
    def get_encrypted_vault(self, user_id: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def save_encrypted_vault(self, user_id: str, payload: str):
        raise NotImplementedError


class SupabaseVaultDB(VaultDB):
    provider = "supabase"

    def __init__(self, url: str, anon_key: str):
        self.client: Client = create_client(url, anon_key)

    def signup(self, email: str, password: str):
        return self.client.auth.sign_up({
            "email": email,
            "password": password,
        })

    def login(self, email: str, password: str):
        return self.client.auth.sign_in_with_password({
            "email": email,
            "password": password,
        })

    def restore_session(self, access_token: str, refresh_token: str):
        """Inject a saved session into the Supabase client so authenticated requests work."""
        self.client.auth.set_session(access_token, refresh_token)

    def refresh_session(self, refresh_token: str):
        return self.client.auth.refresh_session(refresh_token)

    def logout(self):
        return self.client.auth.sign_out()

    def get_encrypted_vault(self, user_id):
        res = self.client.table("vaults") \
            .select("encrypted_vault") \
            .eq("user_id", user_id) \
            .execute()

        if not res.data:
            return ""

        return res.data[0]["encrypted_vault"]

    def save_encrypted_vault(self, user_id: str, payload: str):
        self.client.table("vaults").upsert({
            "user_id": user_id,
            "encrypted_vault": payload,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).execute()


def create_db(config: dict) -> VaultDB:
    provider = config.get("provider")

    if provider == "supabase":
        return SupabaseVaultDB(config["url"], config["anonKey"])

    if provider == "postgresql":
        raise NotImplementedError("PostgreSQL support is planned but not implemented yet.")

    if provider == "sqlite":
        raise NotImplementedError("SQLite support is planned but not implemented yet.")

    raise ValueError(f"Unsupported database provider: {provider}")


_db_instance: VaultDB | None = None


def get_db() -> VaultDB:
    global _db_instance

    if _db_instance is None:
        _db_instance = create_db(load_config())

    return _db_instance


def reset_db():
    global _db_instance
    _db_instance = None


def restore_db_session(access_token: str, refresh_token: str):
    """Inject stored tokens into the active DB client so authenticated queries work."""
    get_db().restore_session(access_token, refresh_token)
