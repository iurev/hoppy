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
