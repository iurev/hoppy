"""Debounce-domain helpers."""

import math
from typing import Any


def make_debounce_token(now_ms: int, pid: int, suffix: str) -> str:
    """Build a stable debounce token from timestamp, process, and suffix."""
    return f"{now_ms}-{pid}-{suffix}"


def normalize_debounce_state(raw_state: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize persisted debounce state into a safe, consistent shape."""
    state = raw_state if isinstance(raw_state, dict) else {}
    raw_last_write = state.get("lastWrite", 0)
    try:
        last_write = float(raw_last_write)
    except (TypeError, ValueError):
        last_write = 0
    return {
        "lastWrite": last_write if math.isfinite(last_write) else 0,
        "lastTarget": state.get("lastTarget") if isinstance(state.get("lastTarget"), str) else None,
        "token": state.get("token") if isinstance(state.get("token"), str) else None,
    }


def should_execute_delayed_switch(token: str, state: dict[str, Any] | None) -> bool:
    """Return whether delayed switch should execute for the given token/state."""
    if not token:
        return False
    normalized = normalize_debounce_state(state)
    last_target = (normalized["lastTarget"] or "").strip()
    return bool(last_target) and normalized["token"] == token
