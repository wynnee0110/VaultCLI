import getpass
import questionary

from vaultcli.core.secret_types import (
    ALL_TYPES,
    TYPE_LABELS,
    TYPE_LOGIN,
    TYPE_API_KEY,
    TYPE_SECURE_NOTE,
    TYPE_SSH_KEY,
    SENSITIVE_FIELDS,
    MULTILINE_FIELDS,
    FIELD_LABELS,
    ALL_FIELDS,
    get_display_summary,
)


# ---------------------------------------------------------------------------
# Simple numeric prompt
# ---------------------------------------------------------------------------

def safe_int(prompt: str, max_index: int) -> int | None:
    """Prompt for a number and validate it's within range. Returns None on bad input."""
    try:
        val = int(input(prompt))
        if val < 0 or val >= max_index:
            print(f"Invalid. Must be 0 – {max_index - 1}.")
            return None
        return val
    except ValueError:
        print("Please enter a number.")
        return None


# ---------------------------------------------------------------------------
# Secret-type selector
# ---------------------------------------------------------------------------

def pick_secret_type() -> str | None:
    """Arrow-key selector for choosing a secret type when adding a new entry."""
    choices = [
        questionary.Choice(title=TYPE_LABELS[t], value=t)
        for t in ALL_TYPES
    ]
    choices.append(questionary.Choice("Cancel", value=None))

    return questionary.select(
        "Secret type:",
        choices=choices,
        use_indicator=True,
        use_shortcuts=True,
    ).ask()


# ---------------------------------------------------------------------------
# Service / account selectors
# ---------------------------------------------------------------------------

def pick_service(services: dict) -> str | None:
    """Keyboard-based selector for choosing a service (arrow keys + enter)."""
    if not services:
        print("\nNo services stored yet.\n")
        return None

    choices = []
    for name in sorted(services.keys()):
        count = len(services[name])
        label = f"{name}  ({count} secret{'s' if count != 1 else ''})"
        choices.append(questionary.Choice(title=label, value=name))

    selected = questionary.select(
        "Select a service:",
        choices=choices,
        use_indicator=True,
        use_shortcuts=True,
    ).ask()

    return selected


def pick_account(accounts: list, service_name: str) -> int | None:
    """Keyboard-based selector for choosing an entry within a service."""
    if not accounts:
        print(f"\n No secrets stored under '{service_name}'.\n")
        return None

    def truncate(text, width=30):
        text = str(text)
        return text if len(text) <= width else text[:width - 3] + "..."

    choices = []
    for i, entry in enumerate(accounts):
        t     = entry.get("secret_type", TYPE_LOGIN)
        label = TYPE_LABELS.get(t, t)
        summary = truncate(get_display_summary(entry))
        choices.append(questionary.Choice(title=f"{summary:<32}  [{label}]", value=i))

    choices.append(questionary.Choice("Cancel", value=-1))

    selected = questionary.select(
        f"Select entry in [{service_name}]:",
        choices=choices,
        use_indicator=True,
        use_shortcuts=True,
    ).ask()

    return selected


# ---------------------------------------------------------------------------
# Entry-collection prompts  (add / edit)
# ---------------------------------------------------------------------------

def _read_field(field: str, current: str = "") -> str:
    """
    Prompt for a single field, respecting sensitivity and multi-line rules.

    - Sensitive fields use getpass (hidden input).
    - Multi-line fields accept multiple lines terminated by a blank line.
    - current != "" → show current value hint and allow blank to keep.
    """
    label = FIELD_LABELS.get(field, field.replace("_", " ").title())
    hint  = f" ({current[:20]}{'...' if len(current) > 20 else ''})" if current else ""

    if field in MULTILINE_FIELDS:
        print(f"{label}{hint} (paste / type, end with a blank line):")
        lines = []
        while True:
            line = input()
            if line == "" and lines:
                break
            lines.append(line)
        value = "\n".join(lines)
        return value if value else current

    if field in SENSITIVE_FIELDS:
        prompt_str = f"{label}{hint}: "
        value = getpass.getpass(prompt_str)
        return value if value else current

    prompt_str = f"{label}{hint}: "
    value = input(prompt_str).strip()
    return value if value else current


def collect_new_entry(secret_type: str) -> dict | None:
    """
    Interactively collect all fields for a brand-new entry of *secret_type*.
    Returns a dict of field→value, or None if the user provided no required data.
    """
    from vaultcli.core.secret_types import REQUIRED_FIELDS
    import uuid

    fields = ALL_FIELDS.get(secret_type, [])
    data: dict = {"secret_type": secret_type}

    print(f"\n  [{TYPE_LABELS.get(secret_type, secret_type)}]")
    for field in fields:
        value = _read_field(field)
        data[field] = value

    # Validate required fields
    required = REQUIRED_FIELDS.get(secret_type, [])
    for req in required:
        if not data.get(req):
            print(f"'{FIELD_LABELS.get(req, req)}' is required.")
            return None

    data["id"] = str(uuid.uuid4())
    return data


def edit_entry(entry: dict) -> dict:
    """
    Interactively edit an existing entry. Blank input keeps the current value.
    Returns the (mutated) entry dict.
    """
    secret_type = entry.get("secret_type", TYPE_LOGIN)
    fields      = ALL_FIELDS.get(secret_type, [])

    print(f"\n  Editing [{TYPE_LABELS.get(secret_type, secret_type)}]  (blank = keep current)")
    for field in fields:
        current = entry.get(field, "")
        value   = _read_field(field, current=current)
        entry[field] = value

    return entry


# ---------------------------------------------------------------------------
# Main menu
# ---------------------------------------------------------------------------

def menu() -> str | None:
    return questionary.select(
        "Vault Menu:",
        choices=[
            questionary.Choice("Add Secret",    value="add"),
            questionary.Choice("View Secrets",  value="view"),
            questionary.Choice("Edit Secret",   value="edit"),
            questionary.Choice("Delete Secret", value="delete"),
            questionary.Choice("Logout",        value="logout"),
            questionary.Choice("Exit",          value="exit"),
        ],
        use_indicator=True,
        use_shortcuts=True,
    ).ask()


def auth_menu() -> str | None:
    print("1. Login")
    print("2. Sign up")
    print("0. Exit")

    choice = input("\nSelect: ").strip()
    return choice
