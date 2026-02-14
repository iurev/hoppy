"""Formatting helpers."""


def normalize_session_row(row: str) -> str:
    """Normalize spacing around tmux session row delimiter."""
    parts = row.split("@")
    if len(parts) < 2:
        return row.strip()

    return " @ ".join(part.strip() for part in parts)


def normalize_session_rows(rows: list[str]) -> list[str]:
    """Normalize each session row while preserving row order."""
    return [normalize_session_row(row) for row in rows]


def add_number_prefixes(items: list[str], limit: int = 9) -> list[str]:
    """Add numeric prefixes to non-special rows up to the configured limit."""
    numbered_items: list[str] = []
    number_index = 1

    for item in items:
        if item.startswith("["):
            numbered_items.append(item)
            continue

        if number_index <= limit:
            numbered_items.append(f"[{number_index}] {item}")
            number_index += 1
            continue

        numbered_items.append(item)

    return numbered_items
