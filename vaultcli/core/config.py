import json
import os
import tempfile


CONFIG_DIR = os.path.expanduser("~/.vaultcli")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
SESSION_FILE = os.path.join(CONFIG_DIR, "session.json")


class ConfigError(RuntimeError):
    """Raised when VaultCLI has not been configured yet."""


def ensure_config_dir():
    os.makedirs(CONFIG_DIR, mode=0o700, exist_ok=True)
    try:
        os.chmod(CONFIG_DIR, 0o700)
    except OSError:
        pass


def ensure_private_file(path: str, mode: int = 0o600):
    if not os.path.exists(path):
        return

    try:
        os.chmod(path, mode)
    except OSError:
        pass


def secure_write_json(path: str, payload: dict, *, indent: int | None = None):
    ensure_config_dir()
    target_dir = os.path.dirname(path) or "."
    fd, temp_path = tempfile.mkstemp(
        prefix=f".{os.path.basename(path)}.",
        dir=target_dir,
        text=True,
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=indent)
            handle.flush()
            os.fsync(handle.fileno())

        ensure_private_file(temp_path)
        os.replace(temp_path, path)
        ensure_private_file(path)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def config_exists() -> bool:
    return os.path.exists(CONFIG_FILE)


def load_config(required: bool = True) -> dict | None:
    ensure_config_dir()

    if not os.path.exists(CONFIG_FILE):
        if required:
            raise ConfigError("VaultCLI is not configured yet. Run `vault init` to configure a provider.")
        return None

    try:
        ensure_private_file(CONFIG_FILE)
        with open(CONFIG_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f"VaultCLI config at {CONFIG_FILE} is not valid JSON. Re-run `vault init`."
        ) from exc

    provider = (data.get("provider") or "").strip().lower()
    if not provider:
        raise ConfigError(
            f"VaultCLI config at {CONFIG_FILE} is incomplete. Missing `provider`."
        )

    # Provider-specific minimal validation keeps configuration flexible and
    # allows adding new adapters without rewriting global config rules.
    if provider == "supabase":
        url = data.get("url")
        anon_key = data.get("anonKey")
        if not url or not anon_key:
            raise ConfigError(
                f"VaultCLI config at {CONFIG_FILE} is incomplete for Supabase. Re-run `vault init`."
            )
    elif provider == "postgresql":
        pg_dsn = data.get("pgDsn")
        if not pg_dsn:
            raise ConfigError(
                f"VaultCLI config at {CONFIG_FILE} is incomplete for PostgreSQL. Missing `pgDsn`."
            )
    elif provider == "custom":
        server_url = data.get("server_url")
        if not server_url:
            raise ConfigError(
                f"VaultCLI config at {CONFIG_FILE} is incomplete for Custom Server. Missing `server_url`."
            )
    elif provider == "aws":
        region = data.get("aws_region")
        client_id = data.get("aws_cognito_client_id")
        table = data.get("aws_dynamodb_table")
        if not region or not client_id or not table:
            raise ConfigError(
                f"VaultCLI config at {CONFIG_FILE} is incomplete for AWS. "
                "Missing 'aws_region', 'aws_cognito_client_id', or 'aws_dynamodb_table'."
            )
    else:
        raise ConfigError(
            f"VaultCLI config at {CONFIG_FILE} has unsupported provider '{provider}'. "
            "Use `supabase`, `custom`, or `aws`."
        )

    return data


def save_config(provider: str, url: str = "", anon_key: str = "", **extra_fields):
    ensure_config_dir()

    payload = {
        "provider": provider,
        "url": url,
        "anonKey": anon_key,
    }
    payload.update(extra_fields)

    secure_write_json(CONFIG_FILE, payload, indent=2)
