from vaultcli.core.secret_types import (
    TYPE_LOGIN,
    TYPE_API_KEY,
    TYPE_SECURE_NOTE,
    TYPE_SSH_KEY,
    TYPE_LABELS,
    ALL_FIELDS,
    FIELD_LABELS,
    SENSITIVE_FIELDS,
    MULTILINE_FIELDS,
)


def show_entry(entry: dict, service_name: str, *, reveal: bool = True):
    """
    Pretty-print a vault entry in a box, adapting to its secret_type.

    Parameters
    ----------
    entry        : the decrypted entry dict
    service_name : parent service / collection name
    reveal       : if False, mask sensitive fields (for future --no-reveal flag)
    """
    secret_type = entry.get("secret_type", TYPE_LOGIN)
    type_label  = TYPE_LABELS.get(secret_type, secret_type)
    fields      = ALL_FIELDS.get(secret_type, [])

    # Collect rows first so we can size the box correctly
    rows: list[tuple[str, str]] = [
        ("Service", service_name),
        ("Type",    type_label),
    ]

    for field in fields:
        label = FIELD_LABELS.get(field, field.replace("_", " ").title())
        value = entry.get(field, "-") or "-"

        if not reveal and field in SENSITIVE_FIELDS:
            value = "****"

        if field in MULTILINE_FIELDS:
            # For multi-line values, display only first line in the table
            first_line = str(value).split("\n")[0]
            extra_lines = str(value).split("\n")[1:]
            rows.append((label, first_line))
            for line in extra_lines:
                rows.append(("",     line))
        else:
            rows.append((label, str(value)))

    # --- Determine column widths ----------------------------------------
    label_w = max(len(r[0]) for r in rows)
    value_w = max(min(len(r[1]), 50) for r in rows)

    def _trunc(text: str, width: int) -> str:
        return text if len(text) <= width else text[:width - 3] + "..."

    total_w = label_w + value_w + 7   # "│ " + label + " │ " + value + " │"

    def row_str(label: str, value: str) -> str:
        return f"│ {label:<{label_w}} │ {_trunc(value, value_w):<{value_w}} │"

    separator = "├" + "─" * (label_w + 2) + "┼" + "─" * (value_w + 2) + "┤"

    print("\n" + "┌" + "─" * (total_w - 2) + "┐")
    print(f"│ Secret Details{' ' * (total_w - 17)}│")
    print("├" + "─" * (total_w - 2) + "┤")

    for i, (lbl, val) in enumerate(rows):
        print(row_str(lbl, val))

    print("└" + "─" * (label_w + 2) + "┴" + "─" * (value_w + 2) + "┘\n")


# Backward-compat alias used in older call sites
def show_account(acc: dict, service_name: str):
    """Backward-compatible wrapper → delegates to show_entry."""
    show_entry(acc, service_name)
