def show_account(acc: dict, service_name: str):
    """Pretty-print full account details with improved UI."""

    # Box width
    width = 44

    # Helper for aligned rows
    def row(label, value):
        return f"│ {label:<10} │ {value:<27} │"

    print("\n" + "┌" + "─" * (width - 2) + "┐")
    print(f"│ 🔐 Account Details{' ' * (width - 21)}│")
    print("├" + "─" * (width - 2) + "┤")

    print(row("Service", service_name))
    print(row("Username", acc.get("username", "-")))
    print(row("Email", acc.get("email", "-")))
    print(row("Password", acc.get("password", "-")))

    print("└" + "─" * (width - 2) + "┘\n")
