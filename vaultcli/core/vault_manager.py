import uuid

def migrate_vault(vault: dict) -> dict:
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
                "id": acc.get("id", str(uuid.uuid4())),
                "username": acc.get("username", ""),
                "email": acc.get("email", ""),
                "password": acc.get("password", ""),
            }
            services.setdefault(app, []).append(entry)
        vault = {"services": services}
        print("✅ Migration complete.\n")
    elif "services" not in vault:
        vault = {"services": {}}
    return vault


def parse_secret_path(path: str) -> tuple[str, str, str]:
    parts = [part.strip() for part in path.split("/")]
    if len(parts) == 2:
        service_name, username = parts
        if not service_name or not username:
            raise ValueError("Path must look like <service>/<username>.")
        return service_name, username, ""
    if len(parts) == 3:
        service_name, username, email = parts
        if not service_name or (not username and not email):
            raise ValueError(
                "Path must look like <service>/<username>/<email> when using three segments."
            )
        return service_name, username, email
    raise ValueError(
        "Path must look like <service>/<username> or <service>/<username>/<email>."
    )


def find_account_by_path(vault: dict, path: str) -> tuple[dict | None, str, str, str]:
    service_name, username, email = parse_secret_path(path)
    vault = migrate_vault(vault)
    services = vault["services"]
    accounts = services.get(service_name, [])

    match = next(
        (
            acc for acc in accounts
            if acc.get("username", "") == username and acc.get("email", "") == email
        ),
        None,
    )
    return match, service_name, username, email


def format_secret_path(service_name: str, account: dict) -> str:
    username = account.get("username", "").strip()
    email = account.get("email", "").strip()
    path_parts = [service_name, username]
    if email:
        path_parts.append(email)
    return "/".join(path_parts)
