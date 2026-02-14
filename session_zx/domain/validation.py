"""Validation helpers."""

import re

VALID_ACTIONS = (
    "switch",
    "new",
    "rename",
    "detach",
    "kill",
    "kill-single",
    "reload-sessions",
    "popup-switch",
    "worktree-switch",
    "popup-worktree-switch",
    "capital-switch",
    "popup-capital-switch",
)


def validate_action(action: str) -> None:
    """Validate that an action name is allowed."""
    if not isinstance(action, str):
        raise ValueError(f"Action must be a string, got {type(action).__name__}")

    if action not in VALID_ACTIONS:
        allowed = ", ".join(VALID_ACTIONS)
        raise ValueError(f"Invalid action: {action}. Must be one of: {allowed}")


def validate_session_name(session_name: str) -> None:
    """Validate a tmux session name."""
    if not isinstance(session_name, str):
        raise ValueError(
            f"Session name must be a string, got {type(session_name).__name__}"
        )

    if len(session_name) == 0:
        raise ValueError("Session name cannot be empty")

    if len(session_name) > 100:
        raise ValueError(
            f"Session name exceeds max length of 100 (got {len(session_name)})"
        )

    if ":" in session_name:
        raise ValueError("Session name cannot contain colons (:)")

    if "." in session_name:
        raise ValueError("Session name cannot contain periods (.)")

    if "\n" in session_name or "\r" in session_name:
        raise ValueError("Session name cannot contain newlines")

    if "\0" in session_name:
        raise ValueError("Session name cannot contain null bytes")

    if re.search(r"[\x00-\x1F\x7F]", session_name):
        raise ValueError("Session name cannot contain control characters")

    if not re.fullmatch(r"[a-zA-Z0-9_\-\s]+", session_name):
        raise ValueError(
            "Session name can only contain letters, numbers, underscore, hyphen, and spaces"
        )


def validate_fzf_options(value: str, label: str) -> None:
    """Validate fzf options strings."""
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string, got {type(value).__name__}")

    if len(value) > 10000:
        raise ValueError(f"{label} exceeds max length of 10000 characters")

    if "\0" in value:
        raise ValueError(f"{label} cannot contain null bytes")


def validate_header(header: str | None) -> None:
    """Validate an optional fzf header string."""
    if header is None:
        return

    if not isinstance(header, str):
        raise ValueError(f"Header must be a string, got {type(header).__name__}")

    if len(header) > 500:
        raise ValueError("Header exceeds max length of 500 characters")

    if "\n" in header:
        raise ValueError("Header cannot contain newlines")
