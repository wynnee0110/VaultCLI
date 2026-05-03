import json
import os


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


def config_exists() -> bool:
    return os.path.exists(CONFIG_FILE)


def load_config(required: bool = True) -> dict | None:
    ensure_config_dir()

    if not os.path.exists(CONFIG_FILE):
        if required:
            raise ConfigError(
                "VaultCLI is not configured yet. Run `vault init` to connect it to Supabase."
            )
        return None

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f"VaultCLI config at {CONFIG_FILE} is not valid JSON. Re-run `vault init`."
        ) from exc

    provider = data.get("provider")
    url = data.get("url")
    anon_key = data.get("anonKey")

    if not provider or not url or not anon_key:
        raise ConfigError(
            f"VaultCLI config at {CONFIG_FILE} is incomplete. Re-run `vault init`."
        )

    return data


def save_config(provider: str, url: str, anon_key: str):
    ensure_config_dir()

    payload = {
        "provider": provider,
        "url": url,
        "anonKey": anon_key,
    }

    with open(CONFIG_FILE, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    try:
        os.chmod(CONFIG_FILE, 0o600)
    except OSError:
        pass
