"""Debounce-domain helpers."""


def make_debounce_token(now_ms: int, pid: int, suffix: str) -> str:
    """Build a stable debounce token from timestamp, process, and suffix."""
    return f"{now_ms}-{pid}-{suffix}"
