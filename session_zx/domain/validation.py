"""Validation helpers."""

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
