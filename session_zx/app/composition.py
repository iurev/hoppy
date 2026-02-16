"""Composition-root helpers for application dependencies."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import cast

from session_zx.app.context import AppContext

ActionHandler = Callable[[AppContext], int | None]


@dataclass(frozen=True, slots=True)
class AppDependencies:
    """Immutable dependency container used by app routing."""

    action_handlers: dict[str, ActionHandler]


def build_app_dependencies(
    action_handlers: Mapping[object, object] | None = None,
) -> AppDependencies:
    """Build app dependencies with normalized action-handler mappings."""
    if action_handlers is None:
        return AppDependencies(action_handlers={})

    if not isinstance(action_handlers, Mapping):
        raise TypeError("action_handlers must be a mapping")

    normalized_handlers: dict[str, ActionHandler] = {}
    for action, handler in action_handlers.items():
        action_name = str(action)
        if not callable(handler):
            raise TypeError(f"Handler for action {action_name} must be callable")

        normalized_handlers[action_name] = cast(ActionHandler, handler)

    return AppDependencies(action_handlers=normalized_handlers)
