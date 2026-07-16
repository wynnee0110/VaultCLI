from __future__ import annotations

import json
import urllib.request
import urllib.error
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from dataclasses import dataclass

from supabase import Client, create_client

from vaultcli.core.config import load_config


@dataclass
class AuthSession:
    access_token: str
    refresh_token: str


@dataclass
class AuthUser:
    id: str


@dataclass
class AuthResult:
    session: AuthSession | None = None
    user: AuthUser | None = None


class VaultDB(ABC):
    """Common interface for VaultCLI database adapters."""

    provider: str

    @abstractmethod
    def signup(self, email: str, password: str) -> AuthResult:
        raise NotImplementedError

    @abstractmethod
    def login(self, email: str, password: str) -> AuthResult:
        raise NotImplementedError

    @abstractmethod
    def refresh_session(self, refresh_token: str) -> AuthResult:
        raise NotImplementedError

    @abstractmethod
    def restore_session(self, access_token: str, refresh_token: str):
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

    def signup(self, email: str, password: str) -> AuthResult:
        res = self.client.auth.sign_up({
            "email": email,
            "password": password,
        })
        user = AuthUser(id=res.user.id) if res.user else None
        session = AuthSession(
            access_token=res.session.access_token,
            refresh_token=res.session.refresh_token,
        ) if res.session else None
        return AuthResult(session=session, user=user)

    def login(self, email: str, password: str) -> AuthResult:
        res = self.client.auth.sign_in_with_password({
            "email": email,
            "password": password,
        })
        user = AuthUser(id=res.user.id) if res.user else None
        session = AuthSession(
            access_token=res.session.access_token,
            refresh_token=res.session.refresh_token,
        ) if res.session else None
        return AuthResult(session=session, user=user)

    def restore_session(self, access_token: str, refresh_token: str):
        """Inject a saved session into the Supabase client so authenticated requests work."""
        self.client.auth.set_session(access_token, refresh_token)

    def refresh_session(self, refresh_token: str) -> AuthResult:
        res = self.client.auth.refresh_session(refresh_token)
        user = AuthUser(id=res.user.id) if res.user else None
        session = AuthSession(
            access_token=res.session.access_token,
            refresh_token=res.session.refresh_token,
        ) if res.session else None
        return AuthResult(session=session, user=user)

    def logout(self):
        return self.client.auth.sign_out()

    def get_encrypted_vault(self, user_id: str) -> str:
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


class CustomAPIVaultDB(VaultDB):
    provider = "custom"

    def __init__(self, server_url: str):
        self.server_url = server_url.rstrip("/")
        self.access_token: str | None = None
        self.refresh_token: str | None = None

    def _request(self, endpoint: str, payload: dict | None = None, method: str = "POST") -> dict:
        url = f"{self.server_url}{endpoint}"
        headers = {"Content-Type": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req) as res:
                return json.loads(res.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                body = json.loads(exc.read().decode("utf-8"))
                error_msg = body.get("detail", str(exc))
            except Exception:
                error_msg = str(exc)
            raise RuntimeError(f"API Error: {error_msg}")

    def signup(self, email: str, password: str) -> AuthResult:
        res = self._request("/auth/signup", {"email": email, "password": password})
        return AuthResult(user=AuthUser(id=res["user_id"]))

    def login(self, email: str, password: str) -> AuthResult:
        res = self._request("/auth/login", {"email": email, "password": password})
        self.access_token = res["access_token"]
        self.refresh_token = res["refresh_token"]
        return AuthResult(
            session=AuthSession(access_token=self.access_token, refresh_token=self.refresh_token),
            user=AuthUser(id=res["user_id"]),
        )

    def refresh_session(self, refresh_token: str) -> AuthResult:
        res = self._request("/auth/refresh", {"refresh_token": refresh_token})
        self.access_token = res["access_token"]
        self.refresh_token = res["refresh_token"]
        return AuthResult(
            session=AuthSession(access_token=self.access_token, refresh_token=self.refresh_token),
            user=AuthUser(id=res["user_id"]),
        )

    def restore_session(self, access_token: str, refresh_token: str):
        self.access_token = access_token
        self.refresh_token = refresh_token

    def logout(self):
        try:
            self._request("/auth/logout", method="POST")
        finally:
            self.access_token = None
            self.refresh_token = None

    def get_encrypted_vault(self, user_id: str) -> str:
        res = self._request(f"/vaults/{user_id}", method="GET")
        return res.get("encrypted_vault", "")

    def save_encrypted_vault(self, user_id: str, payload: str):
        self._request(f"/vaults/{user_id}", {"encrypted_vault": payload}, method="PUT")


class AWSVaultDB(VaultDB):
    provider = "aws"

    def __init__(
        self,
        region: str,
        client_id: str,
        table_name: str,
        access_key: str = "",
        secret_key: str = "",
    ):
        self.region = region
        self.client_id = client_id
        self.table_name = table_name
        self.access_key = access_key
        self.secret_key = secret_key
        self.access_token: str | None = None
        self.refresh_token: str | None = None
        self._cognito = None
        self._dynamodb = None

    def _get_cognito_client(self):
        if self._cognito is None:
            try:
                import boto3
            except ImportError:
                raise ImportError(
                    "The 'boto3' package is required for the AWS provider. "
                    "Please install it using: pip install boto3"
                )
            kwargs = {"region_name": self.region}
            if self.access_key and self.secret_key:
                kwargs["aws_access_key_id"] = self.access_key
                kwargs["aws_secret_access_key"] = self.secret_key
            self._cognito = boto3.client("cognito-idp", **kwargs)
        return self._cognito

    def _get_dynamodb_client(self):
        if self._dynamodb is None:
            try:
                import boto3
            except ImportError:
                raise ImportError(
                    "The 'boto3' package is required for the AWS provider. "
                    "Please install it using: pip install boto3"
                )
            kwargs = {"region_name": self.region}
            if self.access_key and self.secret_key:
                kwargs["aws_access_key_id"] = self.access_key
                kwargs["aws_secret_access_key"] = self.secret_key
            self._dynamodb = boto3.resource("dynamodb", **kwargs)
        return self._dynamodb

    def signup(self, email: str, password: str) -> AuthResult:
        try:
            client = self._get_cognito_client()
            res = client.sign_up(
                ClientId=self.client_id,
                Username=email,
                Password=password,
                UserAttributes=[{"Name": "email", "Value": email}],
            )
            return AuthResult(user=AuthUser(id=res["UserSub"]))
        except Exception as exc:
            raise RuntimeError(f"AWS Signup failed: {exc}")

    def login(self, email: str, password: str) -> AuthResult:
        try:
            client = self._get_cognito_client()
            res = client.initiate_auth(
                ClientId=self.client_id,
                AuthFlow="USER_PASSWORD_AUTH",
                AuthParameters={
                    "USERNAME": email,
                    "PASSWORD": password,
                },
            )
            auth_res = res["AuthenticationResult"]
            self.access_token = auth_res["AccessToken"]
            self.refresh_token = auth_res.get("RefreshToken")

            user_res = client.get_user(AccessToken=self.access_token)
            user_id = user_res["Username"]

            return AuthResult(
                session=AuthSession(
                    access_token=self.access_token,
                    refresh_token=self.refresh_token,
                ),
                user=AuthUser(id=user_id),
            )
        except Exception as exc:
            raise RuntimeError(f"AWS Login failed: {exc}")

    def refresh_session(self, refresh_token: str) -> AuthResult:
        try:
            client = self._get_cognito_client()
            res = client.initiate_auth(
                ClientId=self.client_id,
                AuthFlow="REFRESH_TOKEN_AUTH",
                AuthParameters={
                    "REFRESH_TOKEN": refresh_token,
                },
            )
            auth_res = res["AuthenticationResult"]
            self.access_token = auth_res["AccessToken"]
            self.refresh_token = auth_res.get("RefreshToken", refresh_token)

            user_res = client.get_user(AccessToken=self.access_token)
            user_id = user_res["Username"]

            return AuthResult(
                session=AuthSession(
                    access_token=self.access_token,
                    refresh_token=self.refresh_token,
                ),
                user=AuthUser(id=user_id),
            )
        except Exception as exc:
            raise RuntimeError(f"AWS Refresh failed: {exc}")

    def restore_session(self, access_token: str, refresh_token: str):
        self.access_token = access_token
        self.refresh_token = refresh_token

    def logout(self):
        try:
            if self.access_token:
                client = self._get_cognito_client()
                client.global_sign_out(AccessToken=self.access_token)
        except Exception:
            pass
        finally:
            self.access_token = None
            self.refresh_token = None

    def get_encrypted_vault(self, user_id: str) -> str:
        try:
            db = self._get_dynamodb_client()
            table = db.Table(self.table_name)
            res = table.get_item(Key={"user_id": user_id})
            item = res.get("Item")
            if not item:
                return ""
            return item.get("encrypted_vault", "")
        except Exception as exc:
            raise RuntimeError(f"AWS DynamoDB Fetch failed: {exc}")

    def save_encrypted_vault(self, user_id: str, payload: str):
        try:
            db = self._get_dynamodb_client()
            table = db.Table(self.table_name)
            table.put_item(
                Item={
                    "user_id": user_id,
                    "encrypted_vault": payload,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        except Exception as exc:
            raise RuntimeError(f"AWS DynamoDB Save failed: {exc}")


def create_db(config: dict) -> VaultDB:
    provider = config.get("provider")

    if provider == "supabase":
        return SupabaseVaultDB(config["url"], config["anonKey"])

    if provider == "custom":
        return CustomAPIVaultDB(config["server_url"])

    if provider == "aws":
        return AWSVaultDB(
            region=config["aws_region"],
            client_id=config["aws_cognito_client_id"],
            table_name=config["aws_dynamodb_table"],
            access_key=config.get("aws_access_key", ""),
            secret_key=config.get("aws_secret_key", ""),
        )

    if provider == "postgresql":
        raise NotImplementedError("PostgreSQL support is planned but not implemented yet.")

    if provider == "sqlite":
        raise NotImplementedError("SQLite support is planned but not implemented yet.")

    raise ValueError(f"Unsupported database provider: {provider}")


_db_instance: VaultDB | None = None
_db_signature: tuple[str, ...] | None = None


def get_db() -> VaultDB:
    global _db_instance, _db_signature

    config = load_config()
    signature = (
        config.get("provider", ""),
        config.get("url", ""),
        config.get("anonKey", ""),
        config.get("server_url", ""),
        config.get("aws_region", ""),
        config.get("aws_cognito_client_id", ""),
        config.get("aws_dynamodb_table", ""),
    )

    if _db_instance is None or _db_signature != signature:
        _db_instance = create_db(config)
        _db_signature = signature

    return _db_instance


def reset_db():
    global _db_instance, _db_signature
    _db_instance = None
    _db_signature = None


def restore_db_session(access_token: str, refresh_token: str):
    """Inject stored tokens into the active DB client so authenticated queries work."""
    get_db().restore_session(access_token, refresh_token)
