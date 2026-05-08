import getpass
import questionary

def safe_int(prompt: str, max_index: int) -> int | None:
    """Prompt for a number and validate it's within range. Returns None on bad input."""
    try:
        val = int(input(prompt))
        if val < 0 or val >= max_index:
            print(f"❌ Invalid. Must be 0 – {max_index - 1}.")
            return None
        return val
    except ValueError:
        print("❌ Please enter a number.")
        return None

def pick_service(services: dict) -> str | None:
    """Keyboard-based selector (arrow keys + enter)."""
    if not services:
        print("\n⚠️  No services stored yet.\n")
        return None

    # Build choices
    choices = []
    for name in sorted(services.keys()):
        count = len(services[name])
        label = f"{name}  ({count} secret{'s' if count != 1 else ''})"
        choices.append(questionary.Choice(title=label, value=name))

    # Prompt
    selected = questionary.select(
        "📂 Select a service:",
        choices=choices,
        use_indicator=True,
        use_shortcuts=True
    ).ask()

    return selected


def pick_account(accounts: list, service_name: str) -> int | None:
    """Keyboard-based selector for accounts."""
    if not accounts:
        print(f"\n⚠️  No accounts stored under '{service_name}'.\n")
        return None

    def truncate(text, width=25):
        text = str(text)
        return text if len(text) <= width else text[:width - 3] + "..."

    # Build choices
    choices = []
    for i, acc in enumerate(accounts):
        username = truncate(acc.get("username", "-"))
        email = truncate(acc.get("email", "-"))

        label = f"{username:<25}  {email}"
        choices.append(questionary.Choice(title=label, value=i))

    # Optional cancel
    choices.append(questionary.Choice("❌ Cancel", value=-1))

    selected = questionary.select(
        f"👤 Select account in [{service_name}]:",
        choices=choices,
        use_indicator=True,
        use_shortcuts=True
    ).ask()

    return selected

def menu() -> str | None:
    return questionary.select(
        "🔐 Vault Menu:",
        choices=[
            questionary.Choice("Add Secret", value="add"),
            questionary.Choice("View Secrets", value="view"),
            questionary.Choice("Edit Secret", value="edit"),
            questionary.Choice("Delete Secret", value="delete"),
            questionary.Choice("Logout", value="logout"),
            questionary.Choice("Exit", value="exit"),
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
