"""Application action routing helpers."""

from collections.abc import Callable, Mapping
from typing import Final

from session_zx.app.context import AppContext
from session_zx.app.exit_codes import normalize_exit_code
from session_zx.domain.validation import validate_action

ActionHandler = Callable[[AppContext], int | None]

PRE_VALIDATION_HELPER_ACTIONS: Final[frozenset[str]] = frozenset(
    {
        "reload-sessions",
        "kill-single-from-line",
        "switch-from-line",
        "delayed-switch",
    }
)


def dispatch_action(action: str, ctx: AppContext) -> int:
    """Resolve and execute the handler for the requested action."""
    handlers = _get_action_handlers(ctx.deps)
    if action not in PRE_VALIDATION_HELPER_ACTIONS:
        validate_action(action)

    handler = _get_handler(handlers, action)
    return normalize_exit_code(handler(ctx))


def _get_action_handlers(deps: object) -> Mapping[str, ActionHandler]:
    handlers = getattr(deps, "action_handlers", None)
    if not isinstance(handlers, Mapping):
        raise TypeError("Context deps must expose an action_handlers mapping")

    return handlers


def _get_handler(handlers: Mapping[str, ActionHandler], action: str) -> ActionHandler:
    handler = handlers.get(action)
    if handler is None:
        raise ValueError(f"No handler registered for action: {action}")

    if not callable(handler):
        raise TypeError(f"Handler for action {action} must be callable")

    return handler
